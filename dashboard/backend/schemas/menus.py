from pydantic import BaseModel
from typing import Optional


class MenuButtonSchema(BaseModel):
    id: int
    screen_id: int
    text_ru: str
    text_en: str
    callback_data: Optional[str] = None
    url: Optional[str] = None
    row: int = 0
    col: int = 0
    sort_order: int = 0
    button_type: str = "callback"
    is_active: bool = True
    visibility_condition: str = "always"

    class Config:
        from_attributes = True


class MenuButtonCreate(BaseModel):
    text_ru: str
    text_en: str
    callback_data: Optional[str] = None
    url: Optional[str] = None
    row: int = 0
    col: int = 0
    sort_order: int = 0
    button_type: str = "callback"
    is_active: bool = True
    visibility_condition: str = "always"


class MenuButtonUpdate(BaseModel):
    text_ru: Optional[str] = None
    text_en: Optional[str] = None
    callback_data: Optional[str] = None
    url: Optional[str] = None
    row: Optional[int] = None
    col: Optional[int] = None
    sort_order: Optional[int] = None
    button_type: Optional[str] = None
    is_active: Optional[bool] = None
    visibility_condition: Optional[str] = None


class MenuScreenSchema(BaseModel):
    id: int
    slug: str
    name: str
    message_text_ru: Optional[str] = None
    message_text_en: Optional[str] = None
    is_system: bool
    is_active: bool
    buttons: list[MenuButtonSchema] = []

    class Config:
        from_attributes = True


class MenuScreenCreate(BaseModel):
    slug: str
    name: str
    message_text_ru: Optional[str] = None
    message_text_en: Optional[str] = None
    is_system: bool = False
    is_active: bool = True


class MenuScreenUpdate(BaseModel):
    slug: Optional[str] = None
    name: Optional[str] = None
    message_text_ru: Optional[str] = None
    message_text_en: Optional[str] = None
    is_active: Optional[bool] = None


class ButtonReorderItem(BaseModel):
    id: int
    row: int
    col: int
    sort_order: int


class ButtonReorderRequest(BaseModel):
    items: list[ButtonReorderItem]
