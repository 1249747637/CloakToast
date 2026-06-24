import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, Float, Text, DateTime
from sqlalchemy.types import TypeDecorator
from .database import Base

class JSONList(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return json.dumps(value or [])

    def process_result_value(self, value, dialect):
        return json.loads(value) if value else []


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    color_tag = Column(String, default="#1677ff")
    notes = Column(Text, default="")
    proxy_type = Column(String, default="none")
    proxy_host = Column(String, default="")
    proxy_port = Column(Integer, nullable=True)
    proxy_user = Column(String, default="")
    proxy_pass = Column(String, default="")
    timezone = Column(String, default="")
    locale = Column(String, default="zh-CN")
    headless = Column(Boolean, default=False)
    humanize = Column(Boolean, default=True)
    human_preset = Column(String, default="default")
    fingerprint_seed = Column(Integer, nullable=True)
    fp_noise_enabled = Column(Boolean, default=True)
    fp_platform = Column(String, default="")
    fp_hardware_concurrency = Column(Integer, nullable=True)
    fp_device_memory = Column(Integer, nullable=True)
    fp_screen_width = Column(Integer, nullable=True)
    fp_screen_height = Column(Integer, nullable=True)
    fp_taskbar_height = Column(Integer, nullable=True)
    fp_gpu_vendor = Column(String, default="")
    fp_gpu_renderer = Column(String, default="")
    fp_webrtc_ip = Column(String, default="")
    fp_location_lat = Column(Float, nullable=True)
    fp_location_lng = Column(Float, nullable=True)
    fp_storage_quota = Column(Integer, nullable=True)
    fp_fonts_dir = Column(String, default="")
    user_agent = Column(String, default="")
    fp_brand = Column(String, default="")
    fp_brand_version = Column(String, default="")
    fp_platform_version = Column(String, default="")
    extension_paths = Column(JSONList, default=list)
    user_data_dir = Column(String, default="")
    cdp_port = Column(Integer, nullable=True)
    extra_args = Column(JSONList, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class URLTask(Base):
    __tablename__ = "url_tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    urls = Column(JSONList, default=list)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TaskProfile(Base):
    __tablename__ = "task_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, nullable=False)
    profile_id = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending/done/skipped
    notes = Column(Text, default="")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
