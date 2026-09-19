import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import hash_password, verify_password


class TestPasswordHash(unittest.TestCase):

    def test_hash_password_returns_tuple(self):
        result = hash_password("test123456")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        hashed, salt = result
        self.assertTrue(len(hashed) > 0)
        self.assertTrue(len(salt) > 0)

    def test_hash_password_different_salts(self):
        h1, s1 = hash_password("samepassword")
        h2, s2 = hash_password("samepassword")
        self.assertNotEqual(s1, s2)
        self.assertNotEqual(h1, h2)

    def test_hash_password_with_given_salt(self):
        salt = "abc123"
        h1, s1 = hash_password("mypassword", salt)
        h2, s2 = hash_password("mypassword", salt)
        self.assertEqual(s1, salt)
        self.assertEqual(s2, salt)
        self.assertEqual(h1, h2)

    def test_verify_password_correct(self):
        hashed, salt = hash_password("correctpass")
        self.assertTrue(verify_password("correctpass", hashed, salt))

    def test_verify_password_wrong(self):
        hashed, salt = hash_password("correctpass")
        self.assertFalse(verify_password("wrongpass", hashed, salt))

    def test_verify_password_empty(self):
        hashed, salt = hash_password("somepass")
        self.assertFalse(verify_password("", hashed, salt))

    def test_password_unicode(self):
        hashed, salt = hash_password("密码测试123")
        self.assertTrue(verify_password("密码测试123", hashed, salt))
        self.assertFalse(verify_password("错误密码", hashed, salt))

    def test_long_password(self):
        long_pass = "a" * 200
        hashed, salt = hash_password(long_pass)
        self.assertTrue(verify_password(long_pass, hashed, salt))
        self.assertFalse(verify_password("a" * 199, hashed, salt))


if __name__ == "__main__":
    unittest.main()
