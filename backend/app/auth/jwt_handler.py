import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Union
from jose import JWTError, jwt
from app.config import settings

logger = logging.getLogger(__name__)

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def create_access_token(
    subject: Union[str, Dict[str, Any]],
    extra_claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a signed JWT access token."""
    claims = {}
    if isinstance(subject, dict):
        claims = subject.copy()
        sub = str(claims.pop("sub", ""))
    else:
        sub = str(subject)

    if extra_claims:
        claims.update(extra_claims)

    if expires_delta:
        expire = _utcnow() + expires_delta
    else:
        expire = _utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": sub,
        "exp": expire,
        "iat": _utcnow(),
        "type": "access",
        **claims
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(subject: str) -> str:
    """Create a JWT refresh token."""
    expire = _utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload: Dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": _utcnow(),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT token. Returns payload or None on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        return None

def get_token_subject(token: str) -> Optional[str]:
    """Extract the 'sub' claim from a token without raising."""
    payload = decode_token(token)
    return payload.get("sub") if payload else None
