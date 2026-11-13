import pytest
from app.auth.password import hash_password, verify_password
from app.auth.jwt_handler import create_access_token, create_refresh_token, decode_token

def test_password_hashing():
    raw = "SecureP@ssw0rd!123"
    hashed = hash_password(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

def test_jwt_token_flow():
    user_payload = {"sub": "user_12345", "role": "researcher", "email": "test@leadintel.io"}
    token = create_access_token(user_payload)
    assert isinstance(token, str)
    assert len(token) > 20

    decoded = decode_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user_12345"
    assert decoded["role"] == "researcher"
    assert decoded["type"] == "access"

def test_jwt_invalid_token():
    invalid_token = "invalid.bearer.jwt_string"
    assert decode_token(invalid_token) is None
