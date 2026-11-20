from datetime import datetime, timezone, timedelta

import jwt

from app.config import settings


def create_access_token(user_id: int) -> str:
    """创建JWT token"""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)

    payload = {"user_id": user_id, "exp": expire} # exp是固定的key不能写expire

    return jwt.encode(
        payload=payload, key=settings.JWT_SECRET_KEY.get_secret_value(), algorithm=settings.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> dict:
    """解析JWT token"""
    return jwt.decode(
        token,
        key=settings.JWT_SECRET_KEY.get_secret_value(),
        algorithms=[settings.JWT_ALGORITHM],
    )
