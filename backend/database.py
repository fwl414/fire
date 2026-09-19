from __future__ import annotations

from datetime import datetime
from typing import Optional
import hashlib
import secrets
import json
import sys

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, JSON, Date,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./fire_ai_agent.db")

IS_SQLITE = DATABASE_URL.startswith("sqlite")
IS_POSTGRESQL = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")

_engine_kwargs = {
    "echo": False,
    "pool_recycle": 1800,
}

if IS_SQLITE:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = int(os.environ.get("DB_POOL_SIZE", "20"))
    _engine_kwargs["max_overflow"] = int(os.environ.get("DB_MAX_OVERFLOW", "50"))
    _engine_kwargs["pool_timeout"] = int(os.environ.get("DB_POOL_TIMEOUT", "30"))
    _engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return hashed, salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    test_hash, _ = hash_password(password, salt)
    return test_hash == hashed


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    device_code = Column(String(64), unique=True, index=True, nullable=False)
    device_name = Column(String(128), nullable=False)
    device_type = Column(String(64), default="烟感探测器", index=True)
    location = Column(String(255), default="")
    status = Column(String(32), default="正常", index=True)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True, index=True)
    floor_id = Column(Integer, ForeignKey("floors.id"), nullable=True)
    floor_x = Column(Float, default=0.0)
    floor_y = Column(Float, default=0.0)
    install_date = Column(Date, nullable=True)
    last_maintenance = Column(Date, nullable=True)
    next_maintenance = Column(Date, nullable=True)
    description = Column(Text, default="")
    last_inspection_time = Column(DateTime, nullable=True)
    # 设备接入身份：密钥仅签发时返回一次，列表接口一律脱敏
    device_secret = Column(String(128), default="")
    secret_issued_at = Column(DateTime, nullable=True)
    ingest_enabled = Column(Boolean, default=True)
    last_seen_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class VideoChannel(Base):
    """视频通道台账：摄像头 / NVR 通道的真实接入信息。

    - `password_cipher` 为对称加密后的凭证，任何接口都不回传明文
    - 抓拍地址只保存 `snapshot_path`（由 host+port+path 拼接），不接受完整 URL，避免被用作 SSRF 跳板
    - `platform` 决定使用哪个适配器（见 services/video_platform/registry.py）
    """
    __tablename__ = "video_channels"
    __table_args__ = (UniqueConstraint("tenant_id", "channel_code", name="uq_video_channel_code"),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True, index=True)
    channel_code = Column(String(64), nullable=False, index=True)
    channel_name = Column(String(128), default="")
    location = Column(String(255), default="")
    # 接入信息
    platform = Column(String(32), default="generic", index=True)
    protocol = Column(String(16), default="http")
    host = Column(String(255), default="")
    port = Column(Integer, default=80)
    channel_no = Column(String(16), default="1")
    username = Column(String(128), default="")
    password_cipher = Column(Text, default="")
    snapshot_path = Column(String(255), default="")
    rtsp_url = Column(String(512), default="")
    ptz_enabled = Column(Boolean, default=False)
    verify_tls = Column(Boolean, default=False)
    # 运行状态
    enabled = Column(Boolean, default=True, index=True)
    status = Column(String(24), default="unknown", index=True)
    last_probe_at = Column(DateTime, nullable=True)
    last_snapshot_at = Column(DateTime, nullable=True)
    last_error = Column(String(255), default="")
    device_model = Column(String(128), default="")
    remark = Column(Text, default="")
    # GB28181 国标接入（platform='gb28181' 时使用）：
    #   gb_device_id 为设备/通道自身的 20 位国标编码，parent_gb_id 为空表示设备节点、
    #   否则指向所属设备，用一张表同时表达「设备 → 通道」树
    gb_device_id = Column(String(32), default="", index=True)
    parent_gb_id = Column(String(32), default="", index=True)
    manufacturer = Column(String(128), default="")
    sip_register_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class GB26875Device(Base):
    """GB/T 26875 接入设备台账（用户信息传输装置）。

    - `gb_address` 为 12 位十进制国标地址（报文源地址，6 字节 BCD 低字节在前）
    - `device_code` 与 `devices.device_code` 逻辑关联，不建外键：接入设备可能先登记、
      后补建设备档案，用外键会把两者顺序绑死
    - `password_cipher` 为对称加密后的口令（见 services/gb26875/auth.py），接口只回显是否已配置
    """
    __tablename__ = "gb26875_devices"
    __table_args__ = (UniqueConstraint("gb_address", name="uq_gb26875_device_address"),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    device_code = Column(String(64), default="", index=True)
    gb_address = Column(String(16), nullable=False, index=True)
    username = Column(String(64), default="")
    password_cipher = Column(Text, default="")
    # 设备系统类型标识（GB/T 26875.3-2011 表4）
    device_system_type = Column(Integer, default=0)
    enabled = Column(Boolean, default=True, index=True)
    registered = Column(Boolean, default=False)
    last_heartbeat_at = Column(DateTime, nullable=True, index=True)
    remote_ip = Column(String(64), default="")
    remote_port = Column(Integer, nullable=True)
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class DeviceRequestNonce(Base):
    """设备上报 nonce 去重表，用于防止请求重放。"""
    __tablename__ = "device_request_nonces"
    __table_args__ = (UniqueConstraint("device_id", "nonce", name="uq_device_nonce"),)

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, index=True, nullable=False)
    nonce = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class DeviceTelemetry(Base):
    __tablename__ = "device_telemetry"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    device_id = Column(Integer, index=True)
    temperature = Column(Float, default=25.0)
    smoke = Column(Float, default=0.0)
    co = Column(Float, default=0.0)
    battery = Column(Float, default=100.0)
    online = Column(Boolean, default=True)
    # 以下 4 列为后增：硬件本就在上报，但最初建表未落时序表，2026-09-17 补齐。
    # 全部 nullable，老数据保持 null 不编数。
    current = Column(Float, nullable=True)             # A，单相电流
    voltage = Column(Float, nullable=True)             # V
    pressure = Column(Float, nullable=True)            # MPa，消防水压
    remaining_current = Column(Float, nullable=True)   # mA，剩余电流（漏电监测）
    created_at = Column(DateTime, default=datetime.utcnow)


class InspectionRecord(Base):
    __tablename__ = "inspection_records"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    device_id = Column(Integer, nullable=True, index=True)
    device_code = Column(String(64), default="")
    device_name = Column(String(128), default="")
    location = Column(String(255), default="")
    description = Column(Text, default="")
    image_path = Column(String(255), default="")
    hazards = Column(Text, default="[]")
    risk_score = Column(Integer, default=0)
    risk_level = Column(String(32), default="低风险", index=True)
    suggestion = Column(Text, default="")
    report = Column(Text, default="")
    agent_steps = Column(Text, default="[]")
    used_vision_api = Column(Boolean, default=False)
    used_text_model_api = Column(Boolean, default=False)
    model_provider = Column(String(64), default="")
    model_name = Column(String(128), default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class FaultTicket(Base):
    __tablename__ = "fault_tickets"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    record_id = Column(Integer, nullable=True)
    device_id = Column(Integer, nullable=True)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True, index=True)
    building_name = Column(String(128), default="")
    title = Column(String(255), default="")
    description = Column(Text, default="")
    risk_level = Column(String(32), default="")
    priority = Column(String(32), default="medium", index=True)
    ticket_type = Column(String(64), default="", index=True)
    status = Column(String(32), default="待受理", index=True)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    assignee_name = Column(String(64), default="")
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reporter_name = Column(String(64), default="")
    location = Column(String(255), default="")
    deadline = Column(DateTime, nullable=True)
    handle_result = Column(Text, default="")
    # 来源与闭环复查
    source = Column(String(64), default="", index=True)
    review_result = Column(String(32), default="")
    review_note = Column(Text, default="")
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class MaintenanceCompany(Base):
    __tablename__ = "maintenance_companies"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    name = Column(String(128), nullable=False)
    qualification = Column(String(64), default="")
    level = Column(String(32), default="")
    contact = Column(String(64), default="")
    phone = Column(String(32), default="")
    address = Column(String(255), default="")
    contract_start = Column(Date, nullable=True)
    contract_end = Column(Date, nullable=True)
    status = Column(String(32), default="active")
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class MaintenancePlan(Base):
    __tablename__ = "maintenance_plans"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    plan_no = Column(String(64), unique=True, index=True, nullable=False)
    plan_name = Column(String(128), nullable=False)
    type = Column(String(32), default="monthly")
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    company_id = Column(Integer, ForeignKey("maintenance_companies.id"), nullable=True)
    device_count = Column(Integer, default=0)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    next_date = Column(Date, nullable=True)
    content = Column(Text, default="")
    status = Column(String(32), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    record_no = Column(String(64), unique=True, index=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("maintenance_plans.id"), nullable=True)
    plan_name = Column(String(128), default="")
    type = Column(String(32), default="monthly")
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    building_name = Column(String(128), default="")
    company_id = Column(Integer, ForeignKey("maintenance_companies.id"), nullable=True)
    device_count = Column(Integer, default=0)
    fault_count = Column(Integer, default=0)
    maintainer = Column(String(64), default="")
    maintain_date = Column(Date, nullable=True)
    result = Column(String(32), default="normal")
    content = Column(Text, default="")
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class DutyShift(Base):
    __tablename__ = "duty_shifts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    shift_name = Column(String(64), nullable=False)
    shift_type = Column(String(32), default="day")
    start_time = Column(String(16), default="08:00")
    end_time = Column(String(16), default="20:00")
    duty_date = Column(Date, nullable=True, index=True)
    persons = Column(Text, default="[]")
    status = Column(String(32), default="active")
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class DutyRecord(Base):
    __tablename__ = "duty_records"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    record_date = Column(Date, nullable=True, index=True)
    shift_id = Column(Integer, nullable=True)
    shift_name = Column(String(64), default="")
    duty_person = Column(String(64), default="")
    weather = Column(String(32), default="")
    alarm_count = Column(Integer, default=0)
    handled_count = Column(Integer, default=0)
    inspection_count = Column(Integer, default=0)
    abnormal_count = Column(Integer, default=0)
    equipment_status = Column(String(32), default="normal")
    content = Column(Text, default="")
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class DutyHandover(Base):
    __tablename__ = "duty_handovers"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    handover_time = Column(DateTime, default=datetime.utcnow)
    shift_id = Column(Integer, nullable=True)
    from_person = Column(String(64), default="")
    to_person = Column(String(64), default="")
    handover_items = Column(Text, default="[]")
    pending_matters = Column(Text, default="")
    equipment_status = Column(String(32), default="normal")
    status = Column(String(32), default="completed")
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class KeyUnit(Base):
    __tablename__ = "key_units"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    unit_name = Column(String(256), nullable=False)
    unit_code = Column(String(64), default="")
    industry = Column(String(64), default="")
    level = Column(String(32), default="level2")
    address = Column(String(256), default="")
    legal_person = Column(String(64), default="")
    contact = Column(String(64), default="")
    phone = Column(String(32), default="")
    building_area = Column(Integer, default=0)
    staff_count = Column(Integer, default=0)
    fire_manager = Column(String(64), default="")
    fire_phone = Column(String(32), default="")
    risk_level = Column(String(32), default="medium")
    status = Column(String(32), default="active")
    last_check_date = Column(Date, nullable=True)
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class UnitInspection(Base):
    __tablename__ = "unit_inspections"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    unit_id = Column(Integer, index=True, nullable=False)
    unit_name = Column(String(256), default="")
    inspection_date = Column(Date, nullable=True, index=True)
    inspector = Column(String(64), default="")
    inspection_type = Column(String(64), default="routine")
    items_checked = Column(Integer, default=0)
    items_passed = Column(Integer, default=0)
    problems_found = Column(Integer, default=0)
    rectification_required = Column(Integer, default=0)
    result = Column(String(32), default="qualified")
    content = Column(Text, default="")
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class EmergencyPlan(Base):
    __tablename__ = "emergency_plans"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    plan_name = Column(String(256), nullable=False)
    plan_type = Column(String(64), default="fire")
    plan_level = Column(String(32), default="general")
    building_id = Column(Integer, nullable=True)
    building_name = Column(String(128), default="")
    responsible_person = Column(String(64), default="")
    contact_phone = Column(String(32), default="")
    version = Column(String(32), default="V1.0")
    status = Column(String(32), default="active")
    last_review_date = Column(Date, nullable=True)
    next_review_date = Column(Date, nullable=True)
    content = Column(Text, default="")
    procedures = Column(Text, default="[]")
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class EmergencySupply(Base):
    __tablename__ = "emergency_supplies"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    supply_name = Column(String(128), nullable=False)
    supply_type = Column(String(64), default="equipment")
    specification = Column(String(128), default="")
    quantity = Column(Integer, default=0)
    unit = Column(String(16), default="件")
    location = Column(String(256), default="")
    manager = Column(String(64), default="")
    phone = Column(String(32), default="")
    expire_date = Column(Date, nullable=True)
    status = Column(String(32), default="normal")
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class EmergencyTeam(Base):
    __tablename__ = "emergency_teams"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    team_name = Column(String(128), nullable=False)
    team_type = Column(String(64), default="volunteer")
    leader = Column(String(64), default="")
    leader_phone = Column(String(32), default="")
    member_count = Column(Integer, default=0)
    members = Column(Text, default="[]")
    location = Column(String(256), default="")
    equipment = Column(Text, default="[]")
    status = Column(String(32), default="active")
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class EvacuationRoute(Base):
    __tablename__ = "evacuation_routes"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    route_name = Column(String(128), nullable=False)
    building_id = Column(Integer, nullable=True)
    building_name = Column(String(128), default="")
    floor = Column(String(32), default="")
    start_point = Column(String(256), default="")
    end_point = Column(String(256), default="")
    route_path = Column(Text, default="[]")
    capacity = Column(Integer, default=0)
    distance = Column(Integer, default=0)
    status = Column(String(32), default="active")
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), default="默认配置")
    provider = Column(String(64), index=True, nullable=False)
    base_url = Column(String(512), default="")
    api_key = Column(Text, default="")
    text_model = Column(String(128), default="")
    vision_model = Column(String(128), default="")
    supports_text = Column(Boolean, default=True)
    supports_vision = Column(Boolean, default=False)
    is_active_text = Column(Boolean, default=False)
    is_active_vision = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    tenant_code = Column(String(64), unique=True, index=True, nullable=False)
    tenant_name = Column(String(128), nullable=False)
    contact_name = Column(String(128), default="")
    contact_phone = Column(String(32), default="")
    status = Column(String(32), default="active")
    plan = Column(String(32), default="basic")
    remark = Column(Text, default="")
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class LoginAttemptState(Base):
    """登录失败与锁定状态（持久化，支持重启与多实例共享）。"""
    __tablename__ = "login_attempt_states"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(128), unique=True, index=True, nullable=False)
    fail_count = Column(Integer, default=0)
    lock_until = Column(DateTime, nullable=True)
    last_failed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class LoginLog(Base):
    """登录日志（成功与失败都记）。

    与 `LoginAttemptState` 的区别：后者是「每个用户名一行」的锁定计数聚合，
    本表是逐次尝试明细，供「登录日志」页面查询与安全审计使用。
    设备/浏览器/归属地由 `user_agent` 与 `ip_address` 在读取时解析，不落冗余列。
    """
    __tablename__ = "login_logs"

    id = Column(Integer, primary_key=True, index=True)
    # 未知用户名的失败尝试拿不到租户，留空表示「租户未知」
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    username = Column(String(128), default="", index=True)
    real_name = Column(String(128), default="")
    ip_address = Column(String(64), default="")
    user_agent = Column(String(512), default="")
    status = Column(String(16), default="success", index=True)
    fail_reason = Column(String(255), default="")
    login_at = Column(DateTime, default=datetime.utcnow, index=True)


class RevokedToken(Base):
    """已撤销的访问令牌。仅存储令牌指纹，避免明文令牌落库。"""
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, default=datetime.utcnow)


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    role_code = Column(String(64), unique=True, index=True, nullable=False)
    role_name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    permissions = Column(Text, default="[]")
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    password_salt = Column(String(128), nullable=False)
    real_name = Column(String(128), default="")
    email = Column(String(128), default="")
    phone = Column(String(32), default="")
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True, index=True)
    role = relationship("Role", backref="users")
    department = Column(String(128), default="")
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    organization = relationship("Organization", backref="users")
    avatar = Column(String(255), default="")
    status = Column(String(32), default="active", index=True)
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(64), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    org_code = Column(String(64), unique=True, index=True, nullable=False)
    org_name = Column(String(128), nullable=False)
    parent_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    org_type = Column(String(32), default="company")
    address = Column(String(255), default="")
    contact_name = Column(String(128), default="")
    contact_phone = Column(String(32), default="")
    status = Column(String(32), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    parent = relationship("Organization", backref="children", remote_side=[id])


class Building(Base):
    __tablename__ = "buildings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    building_code = Column(String(64), unique=True, index=True, nullable=False)
    building_name = Column(String(128), nullable=False)
    building_type = Column(String(64), default="office")
    address = Column(String(255), default="")
    latitude = Column(Float, default=0.0)
    longitude = Column(Float, default=0.0)
    floors = Column(Integer, default=1)
    area = Column(Float, default=0.0)
    risk_score = Column(Integer, default=0)
    risk_level = Column(String(32), default="低风险")
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    description = Column(Text, default="")
    status = Column(String(32), default="active", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Floor(Base):
    __tablename__ = "floors"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    building_id = Column(Integer, ForeignKey("buildings.id"), index=True, nullable=False)
    floor_name = Column(String(128), nullable=False)
    floor_number = Column(Integer, default=1)
    floor_plan_image = Column(String(255), default="")
    description = Column(Text, default="")
    status = Column(String(32), default="active", index=True)
    # 该楼层是由哪次 CAD 上传创建的（为空表示手工创建）。
    # 用于"删除历史导入图纸"时定位要一并清理的楼层与设备。
    source_upload_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class UploadedFile(Base):
    """上传文件登记：所有上传内容一律经受控接口下载，按租户隔离。"""
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    category = Column(String(32), index=True, default="misc")
    filename = Column(String(255), default="")
    original_name = Column(String(255), default="")
    file_path = Column(Text, default="")
    media_type = Column(String(128), default="")
    size_bytes = Column(Integer, default=0)
    sha256 = Column(String(64), default="")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner_name = Column(String(64), default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ReportArtifact(Base):
    """后端生成并保存的报表产物登记（含校验指纹，供受控下载与追溯）。"""
    __tablename__ = "report_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    report_no = Column(String(64), unique=True, index=True, nullable=False)
    report_type = Column(String(32), index=True, default="inspection")
    report_format = Column(String(16), default="xlsx")
    title = Column(String(255), default="")
    filename = Column(String(255), default="")
    file_path = Column(Text, default="")
    media_type = Column(String(128), default="")
    size_bytes = Column(Integer, default=0)
    sha256 = Column(String(64), default="")
    params_json = Column(Text, default="{}")
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    generated_by_name = Column(String(64), default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AlertRecord(Base):
    __tablename__ = "alert_records"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    alert_code = Column(String(64), unique=True, index=True, nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    device_code = Column(String(64), default="")
    device_name = Column(String(128), default="")
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True, index=True)
    building_name = Column(String(128), default="")
    location = Column(String(255), default="")
    alert_type = Column(String(64), index=True, nullable=False)
    alert_value = Column(Float, default=0.0)
    alert_unit = Column(String(32), default="")
    severity = Column(String(32), index=True, default="medium")
    status = Column(String(32), default="pending", index=True)
    description = Column(Text, default="")
    agent_analysis = Column(Text, default="")
    workorder_id = Column(Integer, ForeignKey("fault_tickets.id"), nullable=True, index=True)
    # 告警去重/合并/升级
    dedup_key = Column(String(160), index=True, default="")
    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    repeat_count = Column(Integer, default=1)
    merged_into_id = Column(Integer, nullable=True, index=True)
    escalated = Column(Boolean, default=False, index=True)
    escalated_at = Column(DateTime, nullable=True)
    escalation_reason = Column(Text, default="")
    handled_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    handled_at = Column(DateTime, nullable=True)
    handle_result = Column(Text, default="")
    device_info = Column(JSON, default={})
    telemetry_history = Column(JSON, default=[])
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class LlmCallLog(Base):
    """大模型调用日志：记录用量、成本与失败原因，供成本统计与排障。"""
    __tablename__ = "llm_call_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    provider = Column(String(64), default="")
    model = Column(String(128), default="", index=True)
    purpose = Column(String(48), default="", index=True)
    status = Column(String(24), default="success", index=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost = Column(Float, nullable=True)
    currency = Column(String(8), default="USD")
    priced = Column(Boolean, default=False)
    latency_ms = Column(Integer, default=0)
    attempts = Column(Integer, default=1)
    http_status = Column(Integer, nullable=True)
    error = Column(String(512), default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AiReviewTask(Base):
    """AI 分析结果的人工复核任务。

    低可信（云端模型未生效而走了本地兜底）或高风险的 AI 结论不再直接下发工单，
    先落为待复核任务，由人工确认后才生成整改工单，避免假结果自动流入处置流程。
    """
    __tablename__ = "ai_review_tasks"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    source = Column(String(32), default="inspection", index=True)
    record_id = Column(Integer, nullable=True, index=True)
    risk_level = Column(String(24), default="")
    risk_score = Column(Integer, default=0)
    hazards = Column(Text, default="[]")
    confidence = Column(String(16), default="low", index=True)
    reason = Column(String(255), default="")
    ai_summary = Column(Text, default="")
    location = Column(String(255), default="")
    status = Column(String(16), default="pending", index=True)
    ticket_id = Column(Integer, nullable=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewer_name = Column(String(64), default="")
    review_note = Column(Text, default="")
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class DeviceMessage(Base):
    """设备上报消息收件箱（幂等 + 削峰 + 死信）

    改造前设备消息在 MQTT 回调里同步处理：处理失败只记一行日志、既不重试也无从追溯，
    且没有端到端幂等键（设备重发只能靠 nonce 防重放，换一个 nonce 就会重复产生告警）。

    现在：验签仍在回调内同步完成（不能让未验签的数据落库），业务处理改为写入本表后
    交给后台任务队列异步执行，因此具备：
    - **幂等**：`(tenant_id, message_id)` 唯一约束；`message_id` 取设备提供的值，
      未提供时用 `{device_code}:{nonce}` 兜底
    - **削峰**：回调只做验签与落库，业务处理由 worker 按自身节奏消费
    - **重试与死信**：处理失败按任务队列的重试策略重试，超过上限标记为 `dead` 并可重放
    """
    __tablename__ = "device_messages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "message_id", name="uq_device_message_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    message_id = Column(String(128), nullable=False, index=True)
    device_id = Column(Integer, nullable=True, index=True)
    device_code = Column(String(64), default="", index=True)
    kind = Column(String(24), default="", index=True)
    source = Column(String(16), default="mqtt", index=True)
    topic = Column(String(255), default="")
    payload = Column(JSON, default={})
    envelope = Column(JSON, default={})
    # pending / processing / processed / duplicate / failed / dead
    status = Column(String(16), default="pending", index=True)
    attempts = Column(Integer, default=0)
    error = Column(Text, default="")
    alert_id = Column(Integer, nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)


class RuntimeLock(Base):
    """跨实例互斥锁：保证"只应有一个实例执行"的动作不会重复跑。

    用于启动期数据种子、定时备份等场景。多实例部署时各实例都会启动，
    没有这把锁就会出现重复播种、重复备份。靠 `name` 唯一约束 + 过期时间实现。
    """
    __tablename__ = "runtime_locks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False, unique=True, index=True)
    owner = Column(String(96), default="")
    acquired_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True, index=True)


class BackgroundTask(Base):
    """后台任务（持久化作业队列）

    取代此前散落在进程内存里的"任务字典"（重启即丢、无锁、且从同步端点里调用
    `asyncio.create_task` 必然抛 RuntimeError）。

    - 任务落库，进程重启后 pending/running 的任务可被重新领取
    - **抢占式领取**：`UPDATE ... WHERE status='pending'` 按影响行数判定是否抢到，
      不依赖特定方言（SQLite / PostgreSQL 均可用），多实例天然安全
    - **租约**：运行中的任务持有 `lease_expires_at`，worker 崩溃后租约过期即可被其他
      worker 重新领取，不会永久卡在 running
    - `attempts` / `max_attempts` 控制重试；`progress` 与 `result` 供前端轮询
    """
    __tablename__ = "background_tasks"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    task_id = Column(String(64), nullable=False, unique=True, index=True)
    task_type = Column(String(48), nullable=False, index=True)
    task_name = Column(String(255), default="")
    # pending / running / success / failed / canceled
    status = Column(String(16), default="pending", index=True)
    priority = Column(Integer, default=0, index=True)
    payload = Column(JSON, default={})
    result = Column(JSON, default={})
    progress = Column(Integer, default=0)
    progress_message = Column(String(255), default="")
    total_items = Column(Integer, default=0)
    done_items = Column(Integer, default=0)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=1)
    # 租约：谁在跑、跑到什么时候
    lease_owner = Column(String(64), default="")
    lease_expires_at = Column(DateTime, nullable=True, index=True)
    error = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_name = Column(String(64), default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class NotificationChannel(Base):
    """告警的外部通知通道（通用 Webhook / 企业微信 / 钉钉 / 邮件）。

    站内通知由 WebSocket 推送 + 通知中心聚合提供，本表管理的是「推到人」的外部通道。
    `config` 为 JSON，字段随通道类型不同（见 services/alert_notify_service.CHANNEL_TYPES）；
    其中的密钥类字段（secret / password / token）落库前用 video_credential_cipher 加密，
    接口只回显掩码，避免群机器人 Webhook、SMTP 口令明文落库与回传。
    """
    __tablename__ = "notification_channels"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    name = Column(String(128), nullable=False)
    channel_type = Column(String(32), default="webhook", index=True)
    enabled = Column(Boolean, default=True, index=True)
    config = Column(JSON, default=dict)
    # 只推送不低于该级别的告警：low / medium / high / critical
    min_severity = Column(String(16), default="high", index=True)
    # 只推送这些告警类型；空数组表示不限
    alert_types = Column(JSON, default=list)
    last_success_at = Column(DateTime, nullable=True)
    last_error = Column(String(500), default="")
    last_error_at = Column(DateTime, nullable=True)
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class NotificationDelivery(Base):
    """一条告警在某通道上的一次投递记录。

    `(alert_code, channel_id)` 唯一：既做端到端幂等（同一告警同通道只发一次），
    也留一份可排查的发送台账。通道被删除后记录保留（审计需要），因此 channel_id 不建外键。
    """
    __tablename__ = "notification_deliveries"
    __table_args__ = (UniqueConstraint("alert_code", "channel_id", name="uq_notification_delivery"),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    alert_code = Column(String(64), nullable=False, index=True)
    channel_id = Column(Integer, nullable=False, index=True)
    channel_type = Column(String(32), default="")
    # pending / success / failed
    status = Column(String(16), default="pending", index=True)
    attempts = Column(Integer, default=0)
    error = Column(String(500), default="")
    response_excerpt = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class OperationLog(Base):
    """操作日志（审计日志）
    哈希链防篡改：`hash = SHA256(规范化内容 + prev_hash)`，`prev_hash` 指向上一条记录的 hash，
    首条为 64 个 0。任何对历史记录的修改、删除或插入都会导致后续链条校验失败，
    可通过 `GET /api/system/operation-logs/verify` 检出并定位到具体 seq。

    字段语义区分（两套写入方来源不同，不要混用）：
    - `status`：本次请求/执行的最终结果（success / warning / error），由日志中间件写入
    - `level`：业务级别（info / success / warning / danger），由业务代码写入
    """
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    # 哈希链
    seq = Column(Integer, index=True)
    prev_hash = Column(String(64), default="")
    hash = Column(String(64), default="", index=True)
    # 来源：business=业务代码写入，http=日志中间件按请求写入
    source = Column(String(16), default="business", index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(64), default="")
    module = Column(String(64), index=True, default="")
    action = Column(String(64), default="")
    title = Column(String(255), default="")
    description = Column(Text, default="")
    # 业务关联与状态变更
    target_type = Column(String(32), default="", index=True)
    target_id = Column(String(64), default="", index=True)
    level = Column(String(16), default="info", index=True)
    status_before = Column(String(64), default="")
    status_after = Column(String(64), default="")
    link = Column(String(255), default="")
    payload = Column(JSON, default={})
    ip_address = Column(String(64), default="")
    user_agent = Column(String(255), default="")
    request_data = Column(JSON, default={})
    response_data = Column(JSON, default={})
    status = Column(String(32), default="success")
    error_message = Column(Text, default="")
    duration_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class RiskUpdateRecord(Base):
    """风险评分变更记录 - 持久化存储风险评分动态调整历史"""
    __tablename__ = "risk_update_records"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    record_code = Column(String(64), unique=True, index=True, nullable=False)
    building_id = Column(String(128), index=True, default="")
    event_type = Column(String(64), index=True, default="")
    event_data = Column(JSON, default={})
    old_score = Column(Integer, default=0)
    new_score = Column(Integer, default=0)
    change = Column(Integer, default=0)
    reason = Column(Text, default="")
    direction = Column(String(16), default="none")  # up / down / none
    operator = Column(String(64), default="system")
    related_id = Column(String(128), default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class HardwareEvent(Base):
    """硬件事件 - 设备上报的告警/事件记录"""
    __tablename__ = "hardware_events"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    event_code = Column(String(64), unique=True, index=True, nullable=False)
    event_type = Column(String(64), index=True, default="")
    event_name = Column(String(128), default="")
    location = Column(String(255), default="")
    device_id = Column(String(64), default="")
    device_name = Column(String(128), default="")
    description = Column(Text, default="")
    risk_level = Column(String(32), default="medium")
    risk_score = Column(Float, default=0.0)
    status = Column(String(32), default="pending", index=True)
    analysis = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class TrainingPlan(Base):
    """培训计划：一次有组织的培训活动（含对象、讲师、起止日期与进度）"""
    __tablename__ = "training_plans"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    plan_name = Column(String(128), nullable=False)
    plan_type = Column(String(32), default="综合培训", index=True)
    target = Column(String(128), default="")
    trainer = Column(String(64), default="")
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    # 计划人数由用户录入；实际参训人数从 training_records 按 plan_id 聚合得出，不在此冗余存储
    person_count = Column(Integer, default=0)
    progress = Column(Integer, default=0)          # 0-100
    status = Column(String(16), default="pending", index=True)  # pending / ongoing / completed
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class TrainingExam(Base):
    """考试场次定义。

    参考人数、平均分、及格率都是**聚合值**，由 training_records 按 exam_id 现算，
    不做冗余列——否则档案一改就会出现"场次统计与档案对不上"。
    """
    __tablename__ = "training_exams"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    title = Column(String(128), nullable=False)
    description = Column(Text, default="")
    duration_minutes = Column(Integer, default=60)
    question_count = Column(Integer, default=0)
    pass_score = Column(Integer, default=60)
    start_time = Column(DateTime, nullable=True)
    status = Column(String(16), default="pending", index=True)  # pending / ongoing / ended
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class TrainingRecord(Base):
    """培训档案：一个人参加一次培训的记录（含学时、考试成绩与证书编号）"""
    __tablename__ = "training_records"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    trainee_name = Column(String(64), nullable=False, index=True)
    department = Column(String(64), default="", index=True)
    plan_id = Column(Integer, ForeignKey("training_plans.id"), nullable=True, index=True)
    course_name = Column(String(128), default="")
    train_date = Column(Date, nullable=True, index=True)
    study_hours = Column(Float, default=0.0)
    exam_id = Column(Integer, ForeignKey("training_exams.id"), nullable=True, index=True)
    # null 表示还没参加考试（与"考了 0 分"是两件事，不合并）
    exam_score = Column(Float, nullable=True)
    cert_no = Column(String(64), default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


def _migrate_sqlite_columns() -> None:
    """
    SQLite 轻量级自动迁移：为已存在的表补充模型中新增的列。
    仅适用于开发环境；生产环境应使用 Alembic 迁移。
    """
    if not IS_SQLITE:
        return
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
            for col in table.columns:
                if col.name not in existing_cols:
                    col_type = col.type.compile(dialect=engine.dialect)
                    ddl = f'ALTER TABLE {table_name} ADD COLUMN "{col.name}" {col_type}'
                    try:
                        conn.execute(text(ddl))
                    except Exception:
                        pass


def get_default_tenant_id(db: "Session") -> Optional[int]:
    """获取默认租户ID，用于无租户上下文的演示数据初始化。"""
    tenant = db.query(Tenant).filter(Tenant.tenant_code == "default").first()
    return tenant.id if tenant else None


def ensure_auth_state_tables() -> None:
    """确保认证状态表存在（用于未执行启动流程的测试或脚本）。"""
    Base.metadata.create_all(
        bind=engine,
        tables=[LoginAttemptState.__table__, RevokedToken.__table__, LoginLog.__table__],
    )


def _ensure_operation_log_chain_index() -> None:
    """为审计日志的哈希链保证 seq 唯一。

    `_migrate_sqlite_columns` 只补列不补约束，因此对已有库显式建唯一索引；
    并发写入时靠它兜底，冲突方重试取下一个序号。
    """
    from sqlalchemy import text

    try:
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_operation_log_seq ON operation_logs (seq)"
            ))
    except Exception:
        # 索引已存在或方言不支持 IF NOT EXISTS 时忽略，链校验仍可检出异常
        pass


def _run_migrations() -> None:
    """用 Alembic 把数据库结构推到最新版本。

    并发安全与存量库标记的细节见 `services.db_migration_service`；
    迁移失败会直接抛出，不让应用带着不确定的结构启动。
    """
    from services.db_migration_service import migrate_on_startup

    migrate_on_startup()


def init_db() -> None:
    _run_migrations()
    # 权限码补齐必须放在这里：生产分支不会执行种子，但存量生产库同样需要拿到新权限码
    _patch_system_role_permissions()
    if os.environ.get("ENV", "development").lower() in ("production", "prod"):
        _ensure_operation_log_chain_index()
        return
    # 补列必须在建唯一索引之前：已有库要先有 seq 列，索引才能建上
    _migrate_sqlite_columns()
    _ensure_operation_log_chain_index()
    # 多实例部署时各实例都会启动，种子数据只应由一个实例写入
    from services.runtime_lock_service import run_exclusive

    run_exclusive("startup_seed", seed_data, ttl_seconds=180)


# 系统角色定义（种子与权限补齐共用同一份来源）
SYSTEM_ROLES = [
    ("admin", "系统管理员", "全部功能、系统设置、知识库维护", ["*"]),
    ("inspector", "巡检员", "发起智能巡检、查看巡检档案",
     ["dashboard:view", "inspection:run", "records:view", "qa:use", "report:view", "building:view",
      "batch:view", "batch:create"]),
    ("rectifier", "整改负责人", "处理工单、提交复查",
     ["dashboard:view", "workorders:view", "workorders:update", "records:view", "report:view", "building:view"]),
    ("viewer", "查看用户", "只查看总览、档案和报告",
     ["dashboard:view", "records:view", "report:view", "building:view"]),
]

# 后加入的权限码 → 需要补齐的系统角色。
#
# 角色种子受 `Role.count() == 0` 守卫，存量库不会重跑种子，因此新权限码必须在这里
# 单独下发；否则接口一旦接上 require_permission，存量部署会直接 403。
# 只追加列出的码、缺失才补、不做整体覆盖，避免抹掉管理员对系统角色的自定义调整。
SYSTEM_ROLE_PERMISSION_PATCHES = [
    # v12.9.0：批量巡检权限码此前只存在于权限清单，既未接线也未授权
    ("inspector", ("batch:view", "batch:create")),
]


def _patch_system_role_permissions() -> int:
    """把后加入的权限码补进存量库的系统角色。返回补写过的角色数。"""
    patch_map = {}
    for role_code, codes in SYSTEM_ROLE_PERMISSION_PATCHES:
        patch_map.setdefault(role_code, []).extend(codes)
    if not patch_map:
        return 0

    db = SessionLocal()
    try:
        patched = 0
        for role in db.query(Role).filter(Role.is_system == True).all():  # noqa: E712
            codes = patch_map.get(role.role_code)
            if not codes:
                continue
            try:
                current = json.loads(role.permissions or "[]")
            except (TypeError, ValueError):
                current = []
            if not isinstance(current, list):
                current = []
            if "*" in current:
                # 通配符角色天然拥有全部权限，无需补齐
                continue
            missing = [code for code in codes if code not in current]
            if not missing:
                continue
            role.permissions = json.dumps(current + missing)
            patched += 1
        if patched:
            db.commit()
        return patched
    except Exception as exc:  # pragma: no cover - 补齐失败不应阻塞启动
        db.rollback()
        print(f"[warn] 系统角色权限补齐失败：{exc}", file=sys.stderr)
        return 0
    finally:
        db.close()


def seed_data() -> None:
    db = SessionLocal()
    demo_mode = os.environ.get("DEMO_MODE", "false").lower() == "true"
    try:
        default_tenant = db.query(Tenant).filter(Tenant.tenant_code == "default").first()
        if not default_tenant:
            default_tenant = Tenant(
                tenant_code="default",
                tenant_name="默认租户",
                contact_name="系统管理员",
                status="active",
                plan="enterprise",
            )
            db.add(default_tenant)
            db.flush()
        tenant_id = default_tenant.id

        if db.query(Device).count() == 0:
            devices = [
                Device(tenant_id=tenant_id, device_code="EXT-A-001", device_name="A区干粉灭火器", device_type="灭火器", location="实验室A区门口"),
                Device(tenant_id=tenant_id, device_code="HYD-B-001", device_name="B区室内消火栓", device_type="消火栓", location="教学楼B区二楼"),
                Device(tenant_id=tenant_id, device_code="ELE-C-001", device_name="C区配电箱", device_type="配电箱", location="机房C区"),
            ]
            db.add_all(devices)
            db.flush()
            for d in devices:
                db.add(DeviceTelemetry(tenant_id=tenant_id, device_id=d.id, temperature=26.5, smoke=0.02, co=0.01, battery=95, online=True))

        if db.query(ModelConfig).count() == 0:
            configs = [
                ModelConfig(
                    name="智谱清言 GLM",
                    provider="zhipu",
                    base_url="https://open.bigmodel.cn/api/paas/v4",
                    api_key="",
                    text_model="glm-4-flash",
                    vision_model="glm-4v-flash",
                    supports_text=True,
                    supports_vision=True,
                    is_active_text=False,
                    is_active_vision=False,
                    enabled=True,
                    remark="推荐用于中文场景；兼容 OpenAI Chat Completions 格式。"
                ),
                ModelConfig(
                    name="阿里云百炼 Qwen",
                    provider="dashscope",
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                    api_key="",
                    text_model="qwen-plus",
                    vision_model="qwen-vl-plus",
                    supports_text=True,
                    supports_vision=True,
                    enabled=True,
                    remark="通义千问，支持文本与视觉模型。"
                ),
                ModelConfig(
                    name="DeepSeek",
                    provider="deepseek",
                    base_url="https://api.deepseek.com",
                    api_key="",
                    text_model="deepseek-chat",
                    vision_model="",
                    supports_text=True,
                    supports_vision=False,
                    enabled=True,
                    remark="适合文本推理、报告生成；当前不作为视觉模型。"
                ),
                ModelConfig(
                    name="OpenAI",
                    provider="openai",
                    base_url="https://api.openai.com/v1",
                    api_key="",
                    text_model="gpt-4o-mini",
                    vision_model="gpt-4o-mini",
                    supports_text=True,
                    supports_vision=True,
                    enabled=True,
                    remark="OpenAI 官方接口，需可访问对应 API。"
                ),
                ModelConfig(
                    name="Moonshot Kimi",
                    provider="moonshot",
                    base_url="https://api.moonshot.cn/v1",
                    api_key="",
                    text_model="moonshot-v1-8k",
                    vision_model="",
                    supports_text=True,
                    supports_vision=False,
                    enabled=True,
                    remark="适合长文本与知识问答。"
                ),
                ModelConfig(
                    name="OpenRouter",
                    provider="openrouter",
                    base_url="https://openrouter.ai/api/v1",
                    api_key="",
                    text_model="openai/gpt-4o-mini",
                    vision_model="openai/gpt-4o-mini",
                    supports_text=True,
                    supports_vision=True,
                    enabled=True,
                    remark="聚合平台，可选择不同模型。"
                ),
            ]
            db.add_all(configs)

        if db.query(Role).count() == 0:
            roles = [
                Role(tenant_id=tenant_id, role_code=role_code, role_name=role_name,
                     description=description, permissions=json.dumps(permissions), is_system=True)
                for role_code, role_name, description, permissions in SYSTEM_ROLES
            ]
            db.add_all(roles)
            db.flush()

            role_map = {r.role_code: r for r in roles}

            if demo_mode and db.query(User).count() == 0:
                import sys
                users_data = [
                    ("admin", "123456", "系统管理员", "admin", "信息中心"),
                    ("inspector", "123456", "巡检员", "inspector", "安全部"),
                    ("rectifier", "123456", "整改负责人", "rectifier", "运维部"),
                    ("viewer", "123456", "查看用户", "viewer", "办公室"),
                ]
                print("=" * 60, file=sys.stderr)
                print("  DEMO MODE - 演示账号已创建", file=sys.stderr)
                print("=" * 60, file=sys.stderr)
                for username, pwd, real_name, role_code, dept in users_data:
                    hashed, salt = hash_password(pwd)
                    db.add(User(
                        username=username,
                        password_hash=hashed,
                        password_salt=salt,
                        real_name=real_name,
                        role_id=role_map[role_code].id,
                        department=dept,
                        status="active",
                        tenant_id=tenant_id,
                    ))
                    print(f"  {username} / {pwd}  ({real_name} - {role_code})", file=sys.stderr)
                print("=" * 60, file=sys.stderr)
                print("  生产环境请设置 DEMO_MODE=false 禁用演示账号", file=sys.stderr)
                print("=" * 60, file=sys.stderr)

        if db.query(Building).count() == 0:
            buildings = [
                Building(tenant_id=tenant_id, building_code="BLD-001", building_name="综合办公楼A座", building_type="office",
                         address="园区1号", latitude=39.9042, longitude=116.4074,
                         floors=12, area=15000, risk_score=45, risk_level="中风险"),
                Building(tenant_id=tenant_id, building_code="BLD-002", building_name="实验楼B座", building_type="lab",
                         address="园区2号", latitude=39.9055, longitude=116.4088,
                         floors=6, area=8000, risk_score=62, risk_level="高风险"),
                Building(tenant_id=tenant_id, building_code="BLD-003", building_name="学生宿舍C区", building_type="dormitory",
                         address="园区3号", latitude=39.9030, longitude=116.4060,
                         floors=8, area=12000, risk_score=55, risk_level="中风险"),
            ]
            db.add_all(buildings)
            db.flush()

            if db.query(Floor).count() == 0:
                building_map = {b.building_code: b.id for b in buildings}
                floors = []
                for bld_code, bld_id in building_map.items():
                    bld = db.query(Building).filter(Building.building_code == bld_code).first()
                    for i in range(1, min(bld.floors, 4) + 1):
                        floors.append(Floor(
                            tenant_id=tenant_id,
                            building_id=bld_id,
                            floor_name=f"{i}层",
                            floor_number=i,
                            description=f"{bld.building_name} {i}层",
                        ))
                db.add_all(floors)
                db.flush()

                if db.query(Device).count() == 3:
                    floor_map = {}
                    for f in db.query(Floor).all():
                        key = f"{f.building_id}-{f.floor_number}"
                        floor_map[key] = f.id
                    b1_id = building_map.get("BLD-001")
                    b2_id = building_map.get("BLD-002")
                    devices_update = [
                        (1, b1_id, floor_map.get(f"{b1_id}-1"), 120.5, 80.3),
                        (2, b1_id, floor_map.get(f"{b1_id}-2"), 250.8, 150.2),
                        (3, b2_id, floor_map.get(f"{b2_id}-1"), 180.0, 120.0),
                    ]
                    for did, bid, fid, fx, fy in devices_update:
                        dev = db.query(Device).filter(Device.id == did).first()
                        if dev:
                            dev.building_id = bid
                            dev.floor_id = fid
                            dev.floor_x = fx
                            dev.floor_y = fy

        db.commit()

        # 电气火灾监测 / 消防水源监测两个页面依赖的遥测演示点位。
        # 幂等：重复启动不会重复建设备或堆样本；放在这里是因为启动种子走的是本函数，
        # 而 services/demo_seed.py 的 seed_demo_data 只在手动调 /api/demo/seed 时执行。
        from services.demo_seed import seed_telemetry_demo_data

        seed_telemetry_demo_data(db, tenant_id)

        # 消防培训（培训计划 / 考试场次 / 培训档案）的初始数据。
        # 同样是空表才种，用户录入后不会再被追加演示数据。
        from services.training_service import seed_training_demo_data

        seed_training_demo_data(db, tenant_id)
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
