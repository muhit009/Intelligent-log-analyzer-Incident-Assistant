from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.api_key import APIKey
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_api_key,
    hash_api_key,
)
from app.core.dependencies import CurrentUser, RequireAdmin
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    APIKeyCreate,
    APIKeyResponse,
    APIKeyCreatedResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    token = create_access_token(subject=user.username, role=user.role)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: CurrentUser):
    return current_user


@router.post("/users", response_model=UserResponse, status_code=201, dependencies=[RequireAdmin])
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    if body.role not in (UserRole.admin.value, UserRole.viewer.value):
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be '{UserRole.admin.value}' or '{UserRole.viewer.value}'")
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    if body.email:
        existing_email = db.query(User).filter(User.email == body.email).first()
        if existing_email:
            raise HTTPException(status_code=409, detail="Email already taken")
    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/api-keys", response_model=APIKeyCreatedResponse, status_code=201)
def create_api_key(body: APIKeyCreate, current_user: CurrentUser, db: Session = Depends(get_db)):
    raw_key = generate_api_key()
    api_key = APIKey(
        key_hash=hash_api_key(raw_key),
        key_prefix=raw_key[:8],
        name=body.name,
        user_id=current_user.id,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return APIKeyCreatedResponse(
        id=api_key.id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        raw_key=raw_key,
    )


@router.get("/api-keys", response_model=list[APIKeyResponse])
def list_api_keys(current_user: CurrentUser, db: Session = Depends(get_db)):
    keys = db.query(APIKey).filter(APIKey.user_id == current_user.id).all()
    return keys


@router.delete("/api-keys/{key_id}", status_code=204)
def revoke_api_key(key_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    api_key = db.query(APIKey).filter(APIKey.id == key_id, APIKey.user_id == current_user.id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key.is_active = False
    db.commit()
