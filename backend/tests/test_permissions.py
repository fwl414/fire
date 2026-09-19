import unittest
import sys
import os
import json
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import database
from database import Role, SessionLocal, get_default_tenant_id, init_db
from services.auth_service import (
    has_permission,
    get_user_permissions,
    get_user_role,
)


class TestPermissions(unittest.TestCase):

    def setUp(self):
        self.mock_user = MagicMock()
        self.mock_user.id = 1
        self.mock_user.role_id = 1

        self.mock_role = MagicMock()
        self.mock_role.id = 1
        self.mock_role.role_code = "admin"
        self.mock_role.permissions = json.dumps([
            "dashboard",
            "inspection",
            "records",
            "system:users",
            "system:roles",
        ])

        self.mock_db = MagicMock()

    def _setup_role_query(self):
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_role

    def test_get_user_role(self):
        self._setup_role_query()
        role = get_user_role(self.mock_user, self.mock_db)
        self.assertIsNotNone(role)
        self.assertEqual(role.role_code, "admin")

    def test_get_user_role_no_role_id(self):
        self.mock_user.role_id = None
        role = get_user_role(self.mock_user, self.mock_db)
        self.assertIsNone(role)

    def test_get_user_permissions(self):
        self._setup_role_query()
        perms = get_user_permissions(self.mock_user, self.mock_db)
        self.assertIsInstance(perms, list)
        self.assertEqual(len(perms), 5)
        self.assertIn("dashboard", perms)
        self.assertIn("system:users", perms)

    def test_get_user_permissions_no_role(self):
        self.mock_user.role_id = None
        perms = get_user_permissions(self.mock_user, self.mock_db)
        self.assertEqual(perms, [])

    def test_has_permission_true(self):
        self._setup_role_query()
        result = has_permission(self.mock_user, self.mock_db, "dashboard")
        self.assertTrue(result)

    def test_has_permission_false(self):
        self._setup_role_query()
        result = has_permission(self.mock_user, self.mock_db, "nonexistent")
        self.assertFalse(result)

    def test_wildcard_permission(self):
        self.mock_role.permissions = json.dumps(["*"])
        self._setup_role_query()
        self.assertTrue(has_permission(self.mock_user, self.mock_db, "anything"))
        self.assertTrue(has_permission(self.mock_user, self.mock_db, "something:else"))

    def test_empty_permissions(self):
        self.mock_role.permissions = json.dumps([])
        self._setup_role_query()
        self.assertFalse(has_permission(self.mock_user, self.mock_db, "dashboard"))

    def test_invalid_permissions_json(self):
        self.mock_role.permissions = "not valid json"
        self._setup_role_query()
        perms = get_user_permissions(self.mock_user, self.mock_db)
        self.assertEqual(perms, [])

    def test_none_permissions(self):
        self.mock_role.permissions = None
        self._setup_role_query()
        perms = get_user_permissions(self.mock_user, self.mock_db)
        self.assertEqual(perms, [])


class TestSystemRolePermissionPatch(unittest.TestCase):
    """回归守卫：角色种子受 `Role.count() == 0` 守卫，存量库不会重跑，

    因此后加入的权限码必须靠权限补齐下发，否则接口一旦接上 require_permission，
    存量部署会直接 403（批量巡检的 batch:view / batch:create 就是这种情况）。
    """

    PROBE_ROLE = "permission-patch-probe"

    def setUp(self):
        init_db()
        self.db = SessionLocal()
        self.db.query(Role).filter(Role.role_code == self.PROBE_ROLE).delete(synchronize_session=False)
        self.db.add(Role(
            tenant_id=get_default_tenant_id(self.db),
            role_code=self.PROBE_ROLE,
            role_name="权限补丁探针",
            permissions=json.dumps(["dashboard:view"]),
            is_system=True,
        ))
        self.db.commit()
        self.original_patches = database.SYSTEM_ROLE_PERMISSION_PATCHES
        database.SYSTEM_ROLE_PERMISSION_PATCHES = [
            (self.PROBE_ROLE, ("batch:view", "batch:create"))
        ]

    def tearDown(self):
        database.SYSTEM_ROLE_PERMISSION_PATCHES = self.original_patches
        self.db.query(Role).filter(Role.role_code == self.PROBE_ROLE).delete(synchronize_session=False)
        self.db.commit()
        self.db.close()

    def _role(self):
        self.db.expire_all()
        return self.db.query(Role).filter(Role.role_code == self.PROBE_ROLE).one()

    def _permissions(self):
        return json.loads(self._role().permissions)

    def test_inspector_default_grants_batch_codes(self):
        defaults = {code: perms for code, _, _, perms in database.SYSTEM_ROLES}
        self.assertIn("batch:view", defaults["inspector"])
        self.assertIn("batch:create", defaults["inspector"])

    def test_missing_codes_are_appended(self):
        self.assertEqual(database._patch_system_role_permissions(), 1)
        self.assertEqual(self._permissions(), ["dashboard:view", "batch:view", "batch:create"])

    def test_patch_is_idempotent(self):
        database._patch_system_role_permissions()
        self.assertEqual(database._patch_system_role_permissions(), 0)
        self.assertEqual(self._permissions(), ["dashboard:view", "batch:view", "batch:create"])

    def test_wildcard_role_is_skipped(self):
        role = self._role()
        role.permissions = json.dumps(["*"])
        self.db.commit()
        self.assertEqual(database._patch_system_role_permissions(), 0)
        self.assertEqual(self._permissions(), ["*"])

    def test_non_system_role_is_untouched(self):
        role = self._role()
        role.is_system = False
        self.db.commit()
        self.assertEqual(database._patch_system_role_permissions(), 0)
        self.assertEqual(self._permissions(), ["dashboard:view"])


if __name__ == "__main__":
    unittest.main()
