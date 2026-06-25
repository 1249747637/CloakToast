from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ProfileBase(BaseModel):
    name: str
    color_tag: str = "#1677ff"
    notes: str = ""
    proxy_type: str = "none"
    proxy_host: str = ""
    proxy_port: Optional[int] = None
    proxy_user: str = ""
    proxy_pass: str = ""
    timezone: str = ""
    locale: str = "zh-CN"
    headless: bool = False
    humanize: bool = True
    human_preset: str = "default"
    fingerprint_seed: Optional[int] = None
    fp_noise_enabled: bool = True
    fp_platform: str = ""
    fp_hardware_concurrency: Optional[int] = None
    fp_device_memory: Optional[int] = None
    fp_screen_width: Optional[int] = None
    fp_screen_height: Optional[int] = None
    fp_taskbar_height: Optional[int] = None
    fp_gpu_vendor: str = ""
    fp_gpu_renderer: str = ""
    fp_webrtc_ip: str = ""
    fp_location_lat: Optional[float] = None
    fp_location_lng: Optional[float] = None
    fp_storage_quota: Optional[int] = None
    fp_fonts_dir: str = ""
    user_agent: str = ""
    fp_brand: str = ""
    fp_brand_version: str = ""
    fp_platform_version: str = ""
    extension_paths: list[str] = []
    user_data_dir: str = ""
    cdp_port: Optional[int] = None
    extra_args: list[str] = []
    # 流量节约
    block_video: bool = False
    block_image_max_kb: Optional[int] = None  # None=不限制 0=全屏蔽 N=>N KB 时 abort
    # WebRTC 模式
    fp_webrtc_mode: str = ""
    # GeoIP 跟随代理 IP
    geoip: bool = False
    # 中继代理（链式代理）
    relay_proxy_type: str = "none"
    relay_proxy_host: str = ""
    relay_proxy_port: Optional[int] = None
    relay_proxy_user: str = ""
    relay_proxy_pass: str = ""


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(ProfileBase):
    pass


class ProfileResponse(ProfileBase):
    id: str
    created_at: datetime
    updated_at: datetime
    is_running: bool = False
    running_since: Optional[datetime] = None

    model_config = {"from_attributes": True}


class URLTaskBase(BaseModel):
    name: str
    urls: list[str] = []
    notes: str = ""


class URLTaskCreate(URLTaskBase):
    pass


class URLTaskUpdate(URLTaskBase):
    pass


class URLTaskResponse(URLTaskBase):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskProfileResponse(BaseModel):
    id: str
    task_id: str
    profile_id: str
    status: str
    notes: str
    updated_at: datetime
    profile: Optional[ProfileResponse] = None

    model_config = {"from_attributes": True}


class URLTaskDetail(URLTaskResponse):
    profiles: list[TaskProfileResponse] = []
    total_profiles: int = 0
    done_count: int = 0


class AddProfilesRequest(BaseModel):
    profile_ids: list[str]


class UpdateStatusRequest(BaseModel):
    status: str  # pending/done/skipped
    notes: str = ""


class LaunchRequest(BaseModel):
    profile_id: str
    task_id: Optional[str] = None


class SystemInfo(BaseModel):
    installed_version: Optional[str] = None
    license_key: Optional[str] = None


class LicenseRequest(BaseModel):
    license_key: str
