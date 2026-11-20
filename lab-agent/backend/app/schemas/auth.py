from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, value: str):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("密码编码长度不得超过 72 字节")
        return value

class LoginResponse(BaseModel):
    token: str
    user: UserResponse

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[\w.@+-]+$")
    password: str = Field(min_length=10, max_length=72)
    name: str | None = Field(default=None, max_length=50)

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, value: str):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("密码编码长度不得超过 72 字节")
        return value
