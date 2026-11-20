from fastapi import APIRouter, Depends
from app.schemas.auth import LoginRequest, RegisterRequest
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import auth_service
from app.common.response import Response

router = APIRouter(prefix="/auth", tags=["权限验证"])


# post含义：向服务器提交数据，通常用于创建或更新资源。
# 在这里用于登录操作，提交用户名和密码进行验证。
@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """登录"""
    result = auth_service.login(db, data)
    # model_validate()：我要创建一个符合特定规则的 Pydantic 对象。
    # model_dump()：我现在不想继续使用这个 Pydantic 对象，而是想把它的数据拿出来，得到一个普通字典。

    return Response.success(message="登录成功", data=result)


@router.post("/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """注册"""
    auth_service.register(db, data)

    # 返回信息
    return Response.success(message="注册成功")
