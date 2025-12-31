"""Authentication module for JWT validation with Supabase Auth."""
import logging
from typing import Optional
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

# Security scheme for OpenAPI docs
security = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    """Decoded JWT token payload from Supabase."""

    sub: str  # User ID (UUID string)
    email: Optional[str] = None
    aud: str = "authenticated"
    role: str = "authenticated"
    exp: int


class CurrentUser(BaseModel):
    """Current authenticated user context."""

    id: UUID
    email: str
    name: Optional[str] = None

    class Config:
        from_attributes = True


def decode_jwt(token: str) -> Optional[TokenPayload]:
    """Decode and validate a Supabase JWT token.

    Args:
        token: JWT token string

    Returns:
        TokenPayload if valid, None otherwise
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True, "require": ["exp", "sub"]},
        )
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """FastAPI dependency to get the current authenticated user.

    Validates the JWT token and returns the user from the database.
    Creates the user record if it doesn't exist (first login).

    Args:
        credentials: Bearer token from Authorization header
        db: Database session

    Returns:
        CurrentUser with user details

    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode and validate token
    payload = decode_jwt(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get or create user in database
    user_id = UUID(payload.sub)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        # First login - create user record
        user = User(
            id=user_id,
            email=payload.email or f"{user_id}@supabase.user",
            name=None,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"Created new user: {user.email}")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return CurrentUser(
        id=user.id,
        email=user.email,
        name=user.name,
    )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[CurrentUser]:
    """FastAPI dependency for optional authentication.

    Returns the user if a valid token is provided, None otherwise.
    Useful for endpoints that work for both authenticated and anonymous users.
    """
    if not credentials:
        return None

    payload = decode_jwt(credentials.credentials)
    if not payload:
        return None

    user_id = UUID(payload.sub)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        return None

    return CurrentUser(
        id=user.id,
        email=user.email,
        name=user.name,
    )
