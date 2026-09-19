"""初始管理员引导工具

生产环境（DEMO_MODE=false）不会创建任何演示账号，全新数据库建成后没有任何用户，
必须通过本工具创建首个管理员，否则无人可登录。

用法：
    python create_admin.py --username admin --password 'StrongPass123'
    python create_admin.py --username admin --password 'NewPass123' --reset-password
    docker compose exec backend python create_admin.py --username admin --password 'StrongPass123'

参数：
    --username        管理员账号
    --password        管理员密码（至少 8 位，且需同时包含字母与数字）
    --real-name       姓名（默认：系统管理员）
    --tenant-name     租户名称（默认：使用已有默认租户，不存在则创建）
    --reset-password  账号已存在时重置其密码
"""
from __future__ import annotations

import argparse
import json
import sys
from database import (
    Role,
    SessionLocal,
    Tenant,
    User,
    get_default_tenant_id,
    hash_password,
    init_db,
)

WEAK_PASSWORDS = {"123456", "12345678", "password", "admin123", "88888888"}


def validate_password(password: str) -> None:
    if len(password) < 8:
        raise ValueError("密码长度至少 8 位")
    if password.lower() in WEAK_PASSWORDS:
        raise ValueError("密码过于简单，请更换")
    has_letter = any(ch.isalpha() for ch in password)
    has_digit = any(ch.isdigit() for ch in password)
    if not (has_letter and has_digit):
        raise ValueError("密码需同时包含字母与数字")


def ensure_tenant(db, tenant_name: str | None) -> int:
    tenant_id = get_default_tenant_id(db)
    if tenant_id:
        return tenant_id
    name = tenant_name or "默认租户"
    tenant = Tenant(tenant_code="default", tenant_name=name, status="active")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    print(f"[info] 已创建租户：{name}（id={tenant.id}）")
    return tenant.id


def ensure_admin_role(db, tenant_id: int) -> Role:
    role = db.query(Role).filter(Role.role_code == "admin").first()
    if role:
        return role
    role = Role(
        tenant_id=tenant_id,
        role_code="admin",
        role_name="系统管理员",
        description="全部功能、系统设置、知识库维护",
        permissions=json.dumps(["*"]),
        is_system=True,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    print("[info] 已创建角色：系统管理员（权限 *）")
    return role


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="创建初始管理员账号")
    parser.add_argument("--username", required=True, help="管理员账号")
    parser.add_argument("--password", required=True, help="管理员密码")
    parser.add_argument("--real-name", default="系统管理员", help="姓名")
    parser.add_argument("--tenant-name", default=None, help="租户名称（仅在无默认租户时使用）")
    parser.add_argument("--reset-password", action="store_true", help="账号已存在时重置密码")
    args = parser.parse_args(argv)

    try:
        validate_password(args.password)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    init_db()

    db = SessionLocal()
    try:
        tenant_id = ensure_tenant(db, args.tenant_name)
        role = ensure_admin_role(db, tenant_id)

        existing = db.query(User).filter(User.username == args.username).first()
        if existing:
            if not args.reset_password:
                print(
                    f"[error] 账号 {args.username} 已存在；如需重置密码请加 --reset-password",
                    file=sys.stderr,
                )
                return 1
            password_hash, salt = hash_password(args.password)
            existing.password_hash = password_hash
            existing.password_salt = salt
            existing.role_id = role.id
            existing.status = "active"
            existing.tenant_id = existing.tenant_id or tenant_id
            db.commit()
            print(f"[ok] 已重置账号 {args.username} 的密码")
            return 0

        password_hash, salt = hash_password(args.password)
        user = User(
            username=args.username,
            password_hash=password_hash,
            password_salt=salt,
            real_name=args.real_name,
            role_id=role.id,
            status="active",
            tenant_id=tenant_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[ok] 管理员账号创建成功：{args.username}（id={user.id}, tenant_id={tenant_id}）")
        print("[warn] 请妥善保管密码，并尽快在系统中修改为专属口令")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
