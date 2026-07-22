"""Identity API: registro, login/logout, refresh (con Token Rotation) y
autogestión de perfil/settings. Cada handler traduce Schema -> DTO/Command
-> caso de uso -> DTO -> Schema; ningún caso de uso conoce FastAPI ni
Pydantic — mismo principio que el resto de los routers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from geekbaku.application.identity.dto import (
    LoginCommand,
    LogoutCommand,
    RefreshTokenCommand,
    RegisterUserCommand,
    UpdateProfileCommand,
    UpdateSettingsCommand,
)
from geekbaku.application.identity.use_cases.get_current_user import GetCurrentUser
from geekbaku.application.identity.use_cases.login_user import LoginUser
from geekbaku.application.identity.use_cases.logout_user import LogoutUser
from geekbaku.application.identity.use_cases.refresh_access_token import RefreshAccessToken
from geekbaku.application.identity.use_cases.register_user import RegisterUser
from geekbaku.application.identity.use_cases.update_profile import UpdateProfile
from geekbaku.application.identity.use_cases.update_settings import UpdateSettings
from geekbaku.domain.identity.value_objects import Identity
from geekbaku.infrastructure.http import deps
from geekbaku.infrastructure.http.schemas.identity_schemas import (
    AuthResultSchema,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    UpdateProfileRequest,
    UpdateSettingsRequest,
    UserSchema,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    use_case: RegisterUser = Depends(deps.get_register_user_use_case),
) -> UserSchema:
    result = await use_case.execute(
        RegisterUserCommand(email=body.email, username=body.username, password=body.password)
    )
    return UserSchema.model_validate(result, from_attributes=True)


@router.post("/login")
async def login(
    request: Request,
    body: LoginRequest,
    use_case: LoginUser = Depends(deps.get_login_user_use_case),
) -> AuthResultSchema:
    result = await use_case.execute(
        LoginCommand(
            email=body.email,
            password=body.password,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    )
    return AuthResultSchema.model_validate(result, from_attributes=True)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def logout(
    body: LogoutRequest,
    use_case: LogoutUser = Depends(deps.get_logout_user_use_case),
) -> None:
    await use_case.execute(LogoutCommand(refresh_token=body.refresh_token))


@router.post("/refresh")
async def refresh(
    request: Request,
    body: RefreshRequest,
    use_case: RefreshAccessToken = Depends(deps.get_refresh_access_token_use_case),
) -> AuthResultSchema:
    result = await use_case.execute(
        RefreshTokenCommand(
            refresh_token=body.refresh_token,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    )
    return AuthResultSchema.model_validate(result, from_attributes=True)


@router.get("/me")
async def get_me(
    identity: Identity = Depends(deps.get_current_identity),
    use_case: GetCurrentUser = Depends(deps.get_current_user_use_case),
) -> UserSchema:
    result = await use_case.execute(identity.user_id)
    return UserSchema.model_validate(result, from_attributes=True)


@router.patch("/profile")
async def update_profile(
    body: UpdateProfileRequest,
    identity: Identity = Depends(deps.get_current_identity),
    use_case: UpdateProfile = Depends(deps.get_update_profile_use_case),
) -> UserSchema:
    result = await use_case.execute(
        UpdateProfileCommand(
            user_id=str(identity.user_id),
            display_name=body.display_name,
            avatar_url=body.avatar_url,
            bio=body.bio,
        )
    )
    return UserSchema.model_validate(result, from_attributes=True)


@router.patch("/settings")
async def update_settings(
    body: UpdateSettingsRequest,
    identity: Identity = Depends(deps.get_current_identity),
    use_case: UpdateSettings = Depends(deps.get_update_settings_use_case),
) -> UserSchema:
    result = await use_case.execute(
        UpdateSettingsCommand(
            user_id=str(identity.user_id),
            language=body.language,
            theme=body.theme,
            notifications_enabled=body.notifications_enabled,
        )
    )
    return UserSchema.model_validate(result, from_attributes=True)
