from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=150)
    password: str = Field(..., min_length=8)
    email: str | None = None
    role: str = "viewer"


class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class APIKeyResponse(BaseModel):
    id: int
    key_prefix: str
    name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyCreatedResponse(APIKeyResponse):
    raw_key: str
