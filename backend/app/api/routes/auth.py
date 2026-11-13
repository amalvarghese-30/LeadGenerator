from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.auth.dependencies import get_db, get_current_user, get_current_admin
from app.auth.password import hash_password, verify_password
from app.auth.jwt_handler import create_access_token, create_refresh_token, decode_token
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserResponse, RefreshRequest
from app.config import settings
from jose import JWTError
from bson import ObjectId

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _user_to_response(user: dict) -> dict:
    return {
        "id": str(user.get("_id", user.get("id", ""))),
        "email": user["email"],
        "username": user.get("username"),
        "full_name": user.get("full_name"),
        "role": user.get("role", "viewer"),
        "is_active": user.get("is_active", True),
        "avatar_url": user.get("avatar_url"),
        "last_login": user.get("last_login").isoformat() if user.get("last_login") else None,
        "created_at": user.get("created_at", datetime.now(timezone.utc)).isoformat(),
    }


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    user = await db.users.find_one({"email": request.email.lower().strip()})
    if not user or not verify_password(request.password, user.get("hashed_password", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    user_id = str(user["_id"])
    access_token = create_access_token(user_id, {"role": user.get("role", "viewer")})
    refresh_token = create_refresh_token(user_id)

    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.now(timezone.utc)}},
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    # Stateless JWT — client discards token; in production add token blacklist
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return _user_to_response(current_user)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(get_current_admin),
):
    existing = await db.users.find_one({"email": data.email.lower().strip()})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    hashed = hash_password(data.password)
    now = datetime.now(timezone.utc)
    doc = {
        "email": data.email.lower().strip(),
        "username": data.username,
        "hashed_password": hashed,
        "full_name": data.full_name,
        "role": data.role,
        "is_active": True,
        "login_attempts": 0,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _user_to_response(doc)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
        user = await db.users.find_one({"_id": ObjectId(user_id), "is_active": True})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        access_token = create_access_token(user_id, {"role": user.get("role", "viewer")})
        new_refresh = create_refresh_token(user_id)
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
