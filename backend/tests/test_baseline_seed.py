"""baseline seed（生产初始数据引导）测试。

用一套独立的临时空库，避免与 conftest 已 `init_db()`（开发分支会写入
默认租户与系统角色）的主测试库互相干扰，从而真实覆盖「空库首次播种」路径。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import SYSTEM_ROLES, Base, Role, Tenant, User, verify_password
from services.baseline_seed import run_if_empty


@pytest.fixture()
def empty_db(tmp_path):
    db_path = Path(tmp_path) / "baseline_seed.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _counts(db):
    return db.query(Tenant).count(), db.query(Role).count(), db.query(User).count()


def test_creates_tenant_roles_and_admin(empty_db, monkeypatch):
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "StrongPass123")

    result = run_if_empty(empty_db)

    assert result["tenant_created"] is True
    tenant = empty_db.query(Tenant).filter(Tenant.tenant_code == "default").first()
    assert tenant is not None and tenant.id == result["tenant_id"]

    assert sorted(result["roles_created"]) == sorted(code for code, *_ in SYSTEM_ROLES)
    assert empty_db.query(Role).count() == len(SYSTEM_ROLES)

    admin = empty_db.query(User).filter(User.username == "admin").first()
    assert admin is not None
    assert admin.tenant_id == tenant.id
    assert admin.status == "active"
    assert verify_password("StrongPass123", admin.password_hash, admin.password_salt)

    admin_role = empty_db.query(Role).filter(Role.id == admin.role_id).first()
    assert admin_role is not None and admin_role.role_code == "admin"


def test_is_idempotent(empty_db, monkeypatch):
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "StrongPass123")

    run_if_empty(empty_db)
    before = _counts(empty_db)

    second = run_if_empty(empty_db)

    assert _counts(empty_db) == before
    assert second["tenant_created"] is False
    assert second["roles_created"] == []
    assert second["admin"]["created"] is False


def test_skips_admin_when_env_missing(empty_db, monkeypatch):
    monkeypatch.delenv("INITIAL_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)

    result = run_if_empty(empty_db)

    assert result["admin"]["created"] is False
    assert empty_db.query(User).count() == 0
    # 租户与角色是系统可用性的前提，即使不建管理员也必须建出来
    assert empty_db.query(Tenant).count() == 1
    assert empty_db.query(Role).count() == len(SYSTEM_ROLES)


def test_rejects_weak_admin_password(empty_db, monkeypatch):
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "12345678")

    result = run_if_empty(empty_db)

    assert result["admin"]["created"] is False
    assert empty_db.query(User).count() == 0
