from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Any = None


class DeviceCreate(BaseModel):
    device_name: str
    device_type: str = "烟感探测器"
    location: str = ""
    status: str = "正常"
    building_id: Optional[int] = None
    floor_id: Optional[int] = None
    floor_x: float = 0.0
    floor_y: float = 0.0
    install_date: Optional[str] = None
    last_maintenance: Optional[str] = None
    next_maintenance: Optional[str] = None
    description: str = ""


class DeviceUpdate(BaseModel):
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    building_id: Optional[int] = None
    floor_id: Optional[int] = None
    floor_x: Optional[float] = None
    floor_y: Optional[float] = None
    install_date: Optional[str] = None
    last_maintenance: Optional[str] = None
    next_maintenance: Optional[str] = None
    description: Optional[str] = None


class TelemetryCreate(BaseModel):
    device_id: int
    temperature: float = 25.0
    smoke: float = 0.0
    co: float = 0.0
    battery: float = 100.0
    online: bool = True


class ModelConfigCreate(BaseModel):
    name: str = "自定义模型配置"
    provider: str = Field(default="custom", description="zhipu/dashscope/deepseek/openai/moonshot/openrouter/custom")
    base_url: str
    api_key: str
    text_model: str = ""
    vision_model: str = ""
    supports_text: bool = True
    supports_vision: bool = False
    enabled: bool = True
    remark: str = ""


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    text_model: Optional[str] = None
    vision_model: Optional[str] = None
    supports_text: Optional[bool] = None
    supports_vision: Optional[bool] = None
    enabled: Optional[bool] = None
    remark: Optional[str] = None


class ModelTestRequest(BaseModel):
    config_id: Optional[int] = None
    mode: str = "text"  # text / vision
    prompt: str = "请用一句话说明你是否可以正常工作。"


# ========== 消防培训 ==========

class TrainingPlanCreate(BaseModel):
    plan_name: str
    plan_type: str = "综合培训"
    target: str = ""
    trainer: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    person_count: int = 0
    progress: int = 0
    status: str = "pending"
    remark: str = ""


class TrainingPlanUpdate(BaseModel):
    plan_name: Optional[str] = None
    plan_type: Optional[str] = None
    target: Optional[str] = None
    trainer: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    person_count: Optional[int] = None
    progress: Optional[int] = None
    status: Optional[str] = None
    remark: Optional[str] = None


class TrainingExamCreate(BaseModel):
    title: str
    description: str = ""
    duration_minutes: int = 60
    question_count: int = 0
    pass_score: int = 60
    start_time: Optional[str] = None
    status: str = "pending"


class TrainingExamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    question_count: Optional[int] = None
    pass_score: Optional[int] = None
    start_time: Optional[str] = None
    status: Optional[str] = None


class TrainingRecordCreate(BaseModel):
    trainee_name: str
    department: str = ""
    plan_id: Optional[int] = None
    course_name: str = ""
    train_date: Optional[str] = None
    study_hours: float = 0.0
    exam_id: Optional[int] = None
    exam_score: Optional[float] = None
    cert_no: str = ""


class TrainingRecordUpdate(BaseModel):
    trainee_name: Optional[str] = None
    department: Optional[str] = None
    plan_id: Optional[int] = None
    course_name: Optional[str] = None
    train_date: Optional[str] = None
    study_hours: Optional[float] = None
    exam_id: Optional[int] = None
    exam_score: Optional[float] = None
    cert_no: Optional[str] = None
