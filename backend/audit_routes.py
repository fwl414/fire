import sys
import os

sys.path.insert(0, '.')
from main import app

routes = []
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        path = route.path
        methods = route.methods or set()
        name = route.name if hasattr(route, 'name') else ''
        deps = []
        if hasattr(route, 'dependencies') and route.dependencies:
            for d in route.dependencies:
                dep_name = ''
                if hasattr(d, 'dependency'):
                    if hasattr(d.dependency, '__name__'):
                        dep_name = d.dependency.__name__
                    elif hasattr(d.dependency, '__qualname__'):
                        dep_name = d.dependency.__qualname__
                    else:
                        dep_name = str(d.dependency)
                deps.append(dep_name)
        routes.append({
            'path': path,
            'methods': sorted(methods),
            'name': name,
            'deps': deps,
        })

routes.sort(key=lambda x: x['path'])

print('总路由数:', len(routes))
print()

public_routes = []
auth_routes = []
unknown_routes = []

for r in routes:
    path = r['path']
    deps = r['deps']
    has_auth = any('get_current_user' in d or 'require_' in d for d in deps)

    is_public = False
    if path in ['/health', '/docs', '/redoc', '/openapi.json'] or path.startswith('/static/') or path.startswith('/uploads/'):
        is_public = True
    if '/report-verify' in path:
        is_public = True
    if path == '/api/auth/login':
        is_public = True

    if is_public:
        public_routes.append(r)
    elif has_auth:
        auth_routes.append(r)
    else:
        unknown_routes.append(r)

print('=== 公开路由:', len(public_routes), '===')
for r in public_routes:
    print(' ', r['methods'], r['path'])

print()
print('=== 已认证路由:', len(auth_routes), '===')
for r in auth_routes:
    print(' ', r['methods'], r['path'], '- deps:', r['deps'])

print()
print('=== 认证不明确/缺失:', len(unknown_routes), '===')
for r in unknown_routes:
    print(' ', r['methods'], r['path'], '- deps:', r['deps'])

total = len(routes)
non_public = total - len(public_routes)
auth_count = len(auth_routes)
print()
print('认证覆盖率: %d/%d = %.1f%%' % (auth_count, non_public, auth_count/non_public*100 if non_public > 0 else 0))
