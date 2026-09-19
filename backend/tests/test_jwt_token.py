import unittest
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    SECRET_KEY,
    ALGORITHM,
)


class TestJWTToken(unittest.TestCase):

    def setUp(self):
        self.mock_user = MagicMock()
        self.mock_user.id = 1
        self.mock_user.username = "testuser"
        self.mock_user.tenant_id = 1

        self.mock_role = MagicMock()
        self.mock_role.role_code = "admin"

    def test_create_access_token_returns_string(self):
        token = create_access_token(self.mock_user, self.mock_role)
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 0)

    def test_create_refresh_token_returns_string(self):
        token = create_refresh_token(self.mock_user)
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 0)

    def test_decode_access_token_valid(self):
        token = create_access_token(self.mock_user, self.mock_role)
        payload = decode_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "1")
        self.assertEqual(payload["username"], "testuser")
        self.assertEqual(payload["role"], "admin")
        self.assertEqual(payload["type"], "access")

    def test_decode_refresh_token_valid(self):
        token = create_refresh_token(self.mock_user)
        payload = decode_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "1")
        self.assertEqual(payload["type"], "refresh")

    def test_decode_invalid_token(self):
        payload = decode_token("invalid.token.string")
        self.assertIsNone(payload)

    def test_decode_empty_token(self):
        payload = decode_token("")
        self.assertIsNone(payload)

    def test_access_token_has_expiry(self):
        token = create_access_token(self.mock_user, self.mock_role)
        payload = decode_token(token)
        self.assertIn("exp", payload)
        self.assertIn("iat", payload)

    def test_tokens_are_different(self):
        access = create_access_token(self.mock_user, self.mock_role)
        refresh = create_refresh_token(self.mock_user)
        self.assertNotEqual(access, refresh)

    def test_token_without_role(self):
        token = create_access_token(self.mock_user, None)
        payload = decode_token(token)
        self.assertEqual(payload["role"], "")

    def test_different_users_different_tokens(self):
        user1 = MagicMock()
        user1.id = 1
        user1.username = "user1"
        user1.tenant_id = 1

        user2 = MagicMock()
        user2.id = 2
        user2.username = "user2"
        user2.tenant_id = 1

        t1 = create_access_token(user1, None)
        t2 = create_access_token(user2, None)

        self.assertNotEqual(t1, t2)
        p1 = decode_token(t1)
        p2 = decode_token(t2)
        self.assertNotEqual(p1["sub"], p2["sub"])


if __name__ == "__main__":
    unittest.main()
