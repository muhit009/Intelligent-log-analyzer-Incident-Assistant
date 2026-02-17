from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.api_key import APIKey
from app.core.security import decode_access_token, hash_api_key

bearer_scheme = HTTPBearer(auto_error=False)

ROLE_HIERARCHY = {UserRole.admin: 2, UserRole.viewer: 1}


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = None,
) -> User:
    from fastapi import Header

    return _resolve_user(db, credentials, x_api_key)


def _get_current_user_impl(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Depends(lambda x_api_key: x_api_key),
) -> User:
    return _resolve_user(db, credentials, x_api_key)


# Actual implementation used by the dependency
from fastapi import Header


def _current_user_dep(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> User:
    # Try Bearer JWT first
    if credentials:
        try:
            payload = decode_access_token(credentials.credentials)
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        username: str | None = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        user = db.query(User).filter(User.username == username).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
        return user

    # Try API key
    if x_api_key:
        key_hash = hash_api_key(x_api_key)
        api_key = db.query(APIKey).filter(APIKey.key_hash == key_hash, APIKey.is_active.is_(True)).first()
        if not api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")
        user = db.query(User).filter(User.id == api_key.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
        return user

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


CurrentUser = Annotated[User, Depends(_current_user_dep)]


def require_role(minimum_role: UserRole):
    min_level = ROLE_HIERARCHY[minimum_role]

    def _check(current_user: CurrentUser) -> User:
        user_level = ROLE_HIERARCHY.get(UserRole(current_user.role), 0)
        if user_level < min_level:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return Depends(_check)


RequireAdmin = require_role(UserRole.admin)
RequireViewer = require_role(UserRole.viewer)
