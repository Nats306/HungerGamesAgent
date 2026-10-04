from fastapi import APIRouter, Depends

from app.core.security import CurrentUser, get_current_user
from app.schemas import UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser = Depends(get_current_user)):
    """Validates the token and returns the authenticated user.
    Registration, login and logout are handled by Keycloak (OpenID Connect)."""
    return UserOut(id=user.id, username=user.username, email=user.email, roles=user.roles)
