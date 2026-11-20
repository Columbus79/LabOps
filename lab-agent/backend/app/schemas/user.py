from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserResponse(BaseModel):
    id: int
    username: str
    name: str
    role: str
    email: str | None = None
    phone: str | None = None
    avatar: str | None = None
    status: int

    model_config = ConfigDict(from_attributes=True)
    # 在默认情况下，Pydantic 的 model_validate() 主要接受字典等适当的数据输入，而不会自动把任意普通对象的属性当成模型字段来读取。
    # 通过设置 from_attributes=True，Pydantic 会尝试从普通对象的属性中读取数据，从而支持直接传入 ORM 模型实例。但最终得到的还是一个 Pydantic 模型对象的实例。


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[\w.@+-]+$")
    password: str = Field(min_length=10, max_length=72)
    name: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=50)
    avatar: str | None = Field(default=None, max_length=200)
    role: Literal["student", "admin"] = "student"
    status: int = Field(default=1, ge=0, le=1)

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, value: str):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("密码编码长度不得超过 72 字节")
        return value


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=50)
    avatar: str | None = Field(default=None, max_length=200)
    role: Literal["student", "admin"] | None = None
    status: int | None = Field(default=None, ge=0, le=1)


class PasswordUpdateRequest(BaseModel):
    """修改密码的请求参数"""

    old_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=10, max_length=72)

    @field_validator("old_password", "new_password")
    @classmethod
    def password_byte_limit(cls, value: str):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("密码编码长度不得超过 72 字节")
        return value
