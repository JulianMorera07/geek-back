"""Schemas Pydantic del Identity API. Se traducen a/desde los DTOs de
`application/identity/dto.py` en el router — nunca se pasan DTOs
directamente a FastAPI ni Pydantic models a los casos de uso.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(examples=["ash@geekbaku.dev"])
    username: str = Field(examples=["ash_ketchum"])
    password: str = Field(examples=["Pikachu123"])


class LoginRequest(BaseModel):
    email: str = Field(examples=["ash@geekbaku.dev"])
    password: str = Field(examples=["Pikachu123"])


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UpdateProfileRequest(BaseModel):
    display_name: str | None = Field(default=None, examples=["Ash Ketchum"])
    avatar_url: str | None = Field(default=None, examples=["https://cdn.geekbaku.dev/ash.png"])
    bio: str | None = Field(default=None, examples=["Quiero ser el mejor entrenador Pokémon."])


class UpdateSettingsRequest(BaseModel):
    language: str | None = Field(default=None, examples=["es"])
    theme: str | None = Field(default=None, examples=["dark"])
    notifications_enabled: bool | None = None


class ProfileSchema(BaseModel):
    display_name: str
    avatar_url: str | None
    bio: str


class UserSettingsSchema(BaseModel):
    language: str
    theme: str
    notifications_enabled: bool


class RoleSchema(BaseModel):
    id: str
    name: str
    is_system: bool


class UserSchema(BaseModel):
    id: str
    email: str
    username: str
    is_active: bool
    is_verified: bool
    roles: tuple[RoleSchema, ...]
    permissions: tuple[str, ...]
    profile: ProfileSchema
    settings: UserSettingsSchema
    created_at: datetime
    updated_at: datetime


class AccessTokenSchema(BaseModel):
    value: str
    token_type: str
    expires_in: int


class AuthResultSchema(BaseModel):
    access_token: AccessTokenSchema
    refresh_token: str
    user: UserSchema
