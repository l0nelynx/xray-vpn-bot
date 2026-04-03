from pydantic import BaseModel
from typing import Optional


class SquadProfileSchema(BaseModel):
    id: int
    name: str
    squad_id: str
    external_squad_id: str

    class Config:
        from_attributes = True


class SquadProfileCreate(BaseModel):
    name: str
    squad_id: str
    external_squad_id: str


class SquadProfileUpdate(BaseModel):
    name: Optional[str] = None
    squad_id: Optional[str] = None
    external_squad_id: Optional[str] = None
