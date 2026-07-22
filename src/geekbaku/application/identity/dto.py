"""DTOs y Commands del módulo de identidad. Dataclasses congeladas, sin
ninguna dependencia de Pydantic/FastAPI — mismo principio que
`application.catalog.dto`/`application.playback.dto`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# ---------------------------------------------------------------------------
# Commands (entrada)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    email: str
    username: str
    password: str


@dataclass(frozen=True, slots=True)
class LoginCommand:
    email: str
    password: str
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True, slots=True)
class RefreshTokenCommand:
    refresh_token: str
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True, slots=True)
class LogoutCommand:
    refresh_token: str


@dataclass(frozen=True, slots=True)
class UpdateProfileCommand:
    user_id: str
    display_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateSettingsCommand:
    user_id: str
    language: str | None = None
    theme: str | None = None
    notifications_enabled: bool | None = None


# ---------------------------------------------------------------------------
# DTOs (salida)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProfileDTO:
    display_name: str
    avatar_url: str | None
    bio: str


@dataclass(frozen=True, slots=True)
class UserSettingsDTO:
    language: str
    theme: str
    notifications_enabled: bool


@dataclass(frozen=True, slots=True)
class RoleDTO:
    id: str
    name: str
    is_system: bool


@dataclass(frozen=True, slots=True)
class PermissionDTO:
    id: str
    resource: str
    action: str
    description: str


@dataclass(frozen=True, slots=True)
class UserDTO:
    id: str
    email: str
    username: str
    is_active: bool
    is_verified: bool
    roles: tuple[RoleDTO, ...]
    permissions: tuple[str, ...]
    profile: ProfileDTO
    settings: UserSettingsDTO
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AccessTokenDTO:
    value: str
    token_type: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class AuthResultDTO:
    access_token: AccessTokenDTO
    refresh_token: str
    user: UserDTO


__all__ = [
    "AccessTokenDTO",
    "AuthResultDTO",
    "LoginCommand",
    "LogoutCommand",
    "PermissionDTO",
    "ProfileDTO",
    "RefreshTokenCommand",
    "RegisterUserCommand",
    "RoleDTO",
    "UpdateProfileCommand",
    "UpdateSettingsCommand",
    "UserDTO",
    "UserSettingsDTO",
]
