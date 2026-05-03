"""
Security utilities: JWT, password hashing.

Handles authentication and authorization security.
"""

from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# bcrypt with cost factor from settings (requirement: cost >= 10)
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.BCRYPT_ROUNDS
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password with bcrypt (cost factor from settings)."""
    return pwd_context.hash(password)


def create_access_token(
    subject: str | Any,
    email: str,
    role: str,
    expires_delta: timedelta | None = None
) -> str:
    """
    Create JWT access token.

    Args:
        subject: User ID
        email: User email
        role: User role (parent/admin)
        expires_delta: Optional custom expiry

    Returns:
        JWT access token string
    """
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRES)
    )
    to_encode = {
        "sub": str(subject),
        "email": email,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access",
    }
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    subject: str | Any,
    email: str,
    expires_delta: timedelta | None = None
) -> str:
    """
    Create JWT refresh token.

    Args:
        subject: User ID
        email: User email
        expires_delta: Optional custom expiry

    Returns:
        JWT refresh token string
    """
    expire = datetime.utcnow() + (
        expires_delta or timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRES)
    )
    to_encode = {
        "sub": str(subject),
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",
    }
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """
    Decode and verify JWT token.

    Args:
        token: JWT token string

    Returns:
        Token payload dict or None if invalid
    """
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
