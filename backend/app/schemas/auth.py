from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = None
    username: Optional[str] = None
    role: str = "viewer"


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    preferences: Optional[dict] = None


class UserResponse(BaseModel):
    id: str
    email: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool
    avatar_url: Optional[str] = None
    last_login: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}
