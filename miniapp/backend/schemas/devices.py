from pydantic import BaseModel


class DeviceItem(BaseModel):
    hwid: str
    platform: str | None = None
    os_version: str | None = None
    device_model: str | None = None
    user_agent: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class DevicesResponse(BaseModel):
    total: int
    devices: list[DeviceItem]
