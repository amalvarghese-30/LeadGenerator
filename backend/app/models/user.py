from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field
from bson import ObjectId


class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return str(v)


class UserDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    email: str
    username: Optional[str] = None
    hashed_password: str
    full_name: Optional[str] = None
    role: str = "viewer"  # admin | manager | analyst | viewer
    is_active: bool = True
    avatar_url: Optional[str] = None
    login_attempts: int = 0
    locked_until: Optional[datetime] = None
    last_login: Optional[datetime] = None
    preferences: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
