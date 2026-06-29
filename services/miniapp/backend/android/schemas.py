"""Request/response models for the Android API."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=256)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=256)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds for the access token


class UserSummary(BaseModel):
    id: int
    email: str | None
    email_verified: bool
    has_password: bool
    has_telegram: bool


class AuthResponse(BaseModel):
    tokens: TokenPair
    user: UserSummary


class SessionInfo(BaseModel):
    id: int
    family_id: str
    issued_at: str
    expires_at: str
    user_agent: str | None = None
    ip: str | None = None


class SessionsResponse(BaseModel):
    sessions: list[SessionInfo]


class SimpleStatus(BaseModel):
    status: str = "ok"
