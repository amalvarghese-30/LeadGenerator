from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.auth.jwt_handler import decode_token
from app.database.connection import get_database

security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """Dependency that yields the MongoDB database."""
    db = get_database()
    yield db


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Validate JWT and return the current user document."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    try:
        payload = decode_token(credentials.credentials)
        if not payload:
            raise credentials_exception
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type", "access")
        if user_id is None or token_type != "access":
            raise credentials_exception
    except (JWTError, HTTPException):
        raise
    except Exception:
        raise credentials_exception

    from bson import ObjectId
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise credentials_exception

    user = await db.users.find_one({"_id": oid, "is_active": True})
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Require that the current user has admin role."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Admin role required.",
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Optional[dict]:
    """Like get_current_user but returns None instead of raising for unauthenticated requests."""
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials=credentials, db=db)
    except HTTPException:
        return None
