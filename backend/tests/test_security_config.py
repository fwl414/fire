import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def all_routes(app):
    routes = []

    def collect(items):
        for route in items:
            nested = getattr(route, "original_router", None)
            if nested is not None:
                collect(nested.routes)
            else:
                routes.append(route)

    collect(app.routes)
    return routes


def dependency_names(route):
    names = []

    def collect(dependant):
        call = getattr(dependant, "call", None)
        if call is not None:
            names.append(getattr(call, "__name__", getattr(call, "__qualname__", str(call))))
        for child in getattr(dependant, "dependencies", []) or []:
            collect(child)

    collect(getattr(route, "dependant", None))
    return names


def query_param_names(route):
    names = []
    for param in getattr(getattr(route, "dependant", None), "query_params", []) or []:
        name = getattr(param, "name", None) or getattr(getattr(param, "field_info", None), "alias", None)
        if name:
            names.append(name)
    return names


class TestSecurityConfig(unittest.TestCase):

    def test_demo_mode_default_false(self):
        demo_mode = os.environ.get("DEMO_MODE", "false").lower() == "true"
        self.assertFalse(demo_mode, "默认情况下 DEMO_MODE 应为 false")

    def test_jwt_secret_in_production(self):
        env = os.environ.get("ENV", "development").lower()
        is_prod = env in ("production", "prod")
        self.assertFalse(is_prod, "测试环境不应为 production，否则需要 JWT_SECRET_KEY")

    def test_cors_not_star_in_production(self):
        from main import _cors_origins, IS_PRODUCTION
        if IS_PRODUCTION:
            self.assertNotIn("*", _cors_origins, "生产环境 CORS 不能是 *")
        else:
            self.assertIsInstance(_cors_origins, list, "CORS 配置应为列表")

    def test_auth_routes_have_dependencies(self):
        from main import app
        sensitive_paths = [
            "/api/auth/me",
            "/api/auth/change-password",
            "/api/auth/logout",
            "/api/auth/refresh",
        ]
        for route in all_routes(app):
            if hasattr(route, "path") and route.path in sensitive_paths:
                dep_names = dependency_names(route)
                self.assertTrue(
                    any("get_current_user" in n for n in dep_names),
                    f"{route.path} 缺少认证依赖"
                )

    def test_management_routes_require_admin(self):
        from main import app
        admin_paths = [
            "/api/settings/model-providers",
            "/api/tenant/organizations",
            "/api/system/health",
        ]
        protected_count = 0
        total = len(admin_paths)
        for route in all_routes(app):
            if hasattr(route, "path") and route.path in admin_paths:
                dep_names = dependency_names(route)
                if any("get_current_user" in n for n in dep_names) and any("_check" in n or "require_role" in n for n in dep_names):
                    protected_count += 1
        self.assertEqual(
            protected_count, total,
            f"管理路由应该有2层以上依赖（认证+角色），通过数: {protected_count}/{total}"
        )


# 明确允许匿名访问的 /api 路由白名单：登录入口 + 报告二维码验真
PUBLIC_API_PATHS = {
    "/api/auth/login",
    "/api/reports/verify/{report_no}",
    "/api/reports/verify-qr/{report_no}",
}

# 设备直连上报路由：不使用用户 JWT，改由设备密钥 HMAC 签名认证
DEVICE_SIGNED_PATHS = {
    "/api/device-ingest/telemetry",
    "/api/device-ingest/event",
    "/api/device-ingest/heartbeat",
}

# 短时令牌路由：浏览器 <img> 无法携带请求头，改用 query 上的短时签名令牌
TOKEN_SIGNED_PATHS = {
    "/api/video/channels/{channel_id}/snapshot",
}

# 权限矩阵：高风险写操作必须同时具备「登录认证」与「权限/角色」两层依赖
PERMISSION_GUARDED_ENDPOINTS = [
    ("POST", "/api/devices"),
    ("PUT", "/api/devices/{device_id}"),
    ("DELETE", "/api/devices/{device_id}"),
    ("POST", "/api/floors"),
    ("DELETE", "/api/floors/{floor_id}"),
    ("POST", "/api/floors/{floor_id}/plan"),
    ("POST", "/api/workorders"),
    ("POST", "/api/workorders/{order_id}/status"),
    ("POST", "/api/workorders/{ticket_id}/rectify"),
    ("POST", "/api/workorders/{ticket_id}/verify"),
    ("POST", "/api/settings/model-test"),
    ("POST", "/api/system/users"),
    ("DELETE", "/api/system/users/{user_id}"),
    ("POST", "/api/system/users/{user_id}/reset-password"),
    ("POST", "/api/tenant/organizations"),
    ("DELETE", "/api/tenant/organizations/{org_id}"),
]


def _routes_by_endpoint(app):
    """返回 {(method, path): route} 映射。"""
    mapping = {}
    for route in all_routes(app):
        path = getattr(route, "path", "")
        for method in getattr(route, "methods", None) or []:
            mapping[(method.upper(), path)] = route
    return mapping


class TestPermissionMatrix(unittest.TestCase):
    """权限矩阵基线与公开路由白名单。"""

    def test_all_api_routes_require_authentication(self):
        """除白名单与设备签名路由外，所有 /api 路由都必须要求登录认证。"""
        from main import app
        unauthenticated = []
        for route in all_routes(app):
            path = getattr(route, "path", "")
            if not path.startswith("/api"):
                continue
            if path in PUBLIC_API_PATHS or path in DEVICE_SIGNED_PATHS or path in TOKEN_SIGNED_PATHS:
                continue
            if not any("get_current_user" in n for n in dependency_names(route)):
                unauthenticated.append(path)

        self.assertEqual(
            sorted(set(unauthenticated)), [],
            f"以下 /api 路由缺少认证依赖: {sorted(set(unauthenticated))}",
        )

    def test_device_signed_routes_use_device_identity(self):
        """设备上报路由必须使用设备签名认证，且不得回退为用户 JWT。"""
        from main import app
        mapping = _routes_by_endpoint(app)

        for path in DEVICE_SIGNED_PATHS:
            routes = [route for (_, p), route in mapping.items() if p == path]
            self.assertTrue(routes, f"设备接入路由不存在: {path}")
            for route in routes:
                names = dependency_names(route)
                self.assertTrue(
                    any("require_device_identity" in n for n in names),
                    f"{path} 缺少设备签名认证依赖",
                )
                self.assertFalse(
                    any("get_current_user" in n for n in names),
                    f"{path} 不应要求用户 JWT",
                )

    def test_token_signed_routes_use_short_lived_token(self):
        """抓拍类路由不走 JWT，必须强制携带 query 上的短时令牌。"""
        from main import app
        mapping = _routes_by_endpoint(app)

        for path in TOKEN_SIGNED_PATHS:
            routes = [route for (_, p), route in mapping.items() if p == path]
            self.assertTrue(routes, f"短时令牌路由不存在: {path}")
            for route in routes:
                names = dependency_names(route)
                self.assertFalse(
                    any("get_current_user" in n for n in names),
                    f"{path} 不应回退为用户 JWT",
                )
                params = query_param_names(route)
                self.assertIn("token", params, f"{path} 必须强制携带 token 查询参数")

    def test_public_allowlist_is_real_and_explicit(self):
        """白名单条目必须真实存在且确实匿名（防止白名单失效或残留）。"""
        from main import app
        mapping = _routes_by_endpoint(app)
        existing_paths = {path for (_, path) in mapping}

        for path in PUBLIC_API_PATHS:
            self.assertIn(path, existing_paths, f"白名单路由不存在: {path}")

        for (method, path), route in mapping.items():
            if path not in PUBLIC_API_PATHS:
                continue
            names = dependency_names(route)
            self.assertFalse(
                any("get_current_user" in n for n in names),
                f"白名单路由 {method} {path} 不应要求认证，如已收紧请从白名单移除",
            )

    def test_sensitive_write_endpoints_have_permission_guard(self):
        """高风险写操作必须有权限/角色层，而不只是登录认证。"""
        from main import app
        mapping = _routes_by_endpoint(app)

        missing = []
        for method, path in PERMISSION_GUARDED_ENDPOINTS:
            route = mapping.get((method, path))
            if route is None:
                missing.append(f"{method} {path}（路由不存在）")
                continue
            names = dependency_names(route)
            has_auth = any("get_current_user" in n for n in names)
            has_guard = any(("_check" in n) or ("require_role" in n) for n in names)
            if not (has_auth and has_guard):
                missing.append(f"{method} {path}（auth={has_auth}, guard={has_guard}）")

        self.assertEqual(missing, [], f"以下高风险接口缺少权限矩阵保护: {missing}")

    def test_write_endpoints_are_not_anonymous(self):
        """任何写操作（POST/PUT/DELETE/PATCH）都不得匿名可访问。"""
        from main import app
        offenders = []
        for route in all_routes(app):
            path = getattr(route, "path", "")
            if not path.startswith("/api"):
                continue
            if path in PUBLIC_API_PATHS or path in DEVICE_SIGNED_PATHS:
                continue
            methods = {m.upper() for m in (getattr(route, "methods", None) or [])}
            if methods & {"POST", "PUT", "DELETE", "PATCH"}:
                if not any("get_current_user" in n for n in dependency_names(route)):
                    offenders.append((sorted(methods), path))

        self.assertEqual(offenders, [], f"以下写操作可匿名访问: {offenders}")


if __name__ == "__main__":
    unittest.main()
