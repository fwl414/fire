import unittest
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import SessionLocal, LoginAttemptState
from services.auth_service import (
    _check_login_lock,
    _record_login_failure,
    _clear_login_failures,
    MAX_LOGIN_ATTEMPTS,
    LOGIN_LOCK_MINUTES,
)


def _state(username):
    """从数据库读取登录状态，验证锁定信息已持久化。"""
    db = SessionLocal()
    try:
        return db.query(LoginAttemptState).filter(
            LoginAttemptState.username == username.lower()
        ).first()
    finally:
        db.close()


def _expire_lock(username):
    db = SessionLocal()
    try:
        record = db.query(LoginAttemptState).filter(
            LoginAttemptState.username == username.lower()
        ).first()
        record.lock_until = datetime.utcnow() - timedelta(minutes=LOGIN_LOCK_MINUTES + 1)
        db.commit()
    finally:
        db.close()


class TestLoginLock(unittest.TestCase):

    USERNAMES = [
        "newuser", "user1", "user2", "lockuser", "checklockuser",
        "expireuser", "clearuser", "testuser", "fulllockuser", "persistuser",
    ]

    def setUp(self):
        for name in self.USERNAMES:
            _clear_login_failures(name)

    def tearDown(self):
        for name in self.USERNAMES:
            _clear_login_failures(name)

    def test_initial_state_not_locked(self):
        locked, remaining = _check_login_lock("newuser")
        self.assertFalse(locked)
        self.assertEqual(remaining, 0)
        self.assertIsNone(_state("newuser"))

    def test_single_failure_not_locked(self):
        count, locked, remaining = _record_login_failure("user1")
        self.assertEqual(count, 1)
        self.assertFalse(locked)
        self.assertEqual(remaining, 0)

    def test_failure_count_increments(self):
        _record_login_failure("user2")
        count, locked, _ = _record_login_failure("user2")
        self.assertEqual(count, 2)
        self.assertFalse(locked)

    def test_lock_after_max_attempts(self):
        username = "lockuser"
        for i in range(MAX_LOGIN_ATTEMPTS - 1):
            count, locked, _ = _record_login_failure(username)
            self.assertFalse(locked)

        count, locked, remaining = _record_login_failure(username)
        self.assertEqual(count, MAX_LOGIN_ATTEMPTS)
        self.assertTrue(locked)
        self.assertEqual(remaining, LOGIN_LOCK_MINUTES * 60)

    def test_check_lock_when_locked(self):
        username = "checklockuser"
        for _ in range(MAX_LOGIN_ATTEMPTS):
            _record_login_failure(username)

        locked, remaining = _check_login_lock(username)
        self.assertTrue(locked)
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, LOGIN_LOCK_MINUTES * 60)

    def test_lock_after_expire_clears(self):
        username = "expireuser"
        for _ in range(MAX_LOGIN_ATTEMPTS):
            _record_login_failure(username)

        self.assertTrue(_check_login_lock(username)[0])

        _expire_lock(username)

        locked, remaining = _check_login_lock(username)
        self.assertFalse(locked)
        self.assertEqual(remaining, 0)

    def test_clear_failures(self):
        username = "clearuser"
        _record_login_failure(username)
        _record_login_failure(username)

        self.assertEqual(_state(username).fail_count, 2)

        _clear_login_failures(username)

        self.assertIsNone(_state(username))

    def test_case_insensitive_username(self):
        _record_login_failure("TestUser")
        self.assertIsNotNone(_state("TestUser"))

        locked, _ = _check_login_lock("TESTUSER")
        self.assertFalse(locked)

        _clear_login_failures("testuser")
        self.assertIsNone(_state("testuser"))

    def test_locked_user_cannot_login_more(self):
        username = "fulllockuser"
        for _ in range(MAX_LOGIN_ATTEMPTS):
            _record_login_failure(username)

        count, locked, remaining = _record_login_failure(username)
        self.assertGreater(count, MAX_LOGIN_ATTEMPTS)
        self.assertTrue(locked)

    def test_lock_state_is_persisted(self):
        """锁定状态落库，进程重启后依然生效（独立会话可读到）。"""
        username = "persistuser"
        for _ in range(MAX_LOGIN_ATTEMPTS):
            _record_login_failure(username)

        record = _state(username)
        self.assertIsNotNone(record)
        self.assertEqual(record.fail_count, MAX_LOGIN_ATTEMPTS)
        self.assertIsNotNone(record.lock_until)

        self.assertTrue(_check_login_lock(username)[0])


if __name__ == "__main__":
    unittest.main()
