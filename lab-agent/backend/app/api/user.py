from fastapi import APIRouter, Depends, Query
from app.database import get_db
from app.schemas.user import (
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
    PasswordUpdateRequest,
)
from app.models.user import User
from app.dependencies.auth import get_current_admin, get_current_user
from app.services import user_service
from app.common.response import Response
from sqlalchemy.orm import Session

router = APIRouter(prefix="/user", tags=["用户信息接口"])


@router.get("/me")
def get_user_info(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""

    return Response.success(
        message="请求成功", data=user_service.get_user_info(current_user)
    )


"""更新当前用户信息的接口"""


@router.put("/me")
def update_user_info(
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    res = user_service.update_user_info(db, current_user, data)
    return Response.success(message="修改个人信息成功", data=res)


"""更新当前用户密码的接口"""


@router.put("/password")
def update_password(
    data: PasswordUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_service.update_password(db, current_user, data)
    return Response.success(message="密码修改成功")


@router.get("/list", dependencies=[Depends(get_current_admin)])
def get_user_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keywords: str | None = None,
    db: Session = Depends(get_db),
) -> Response:
    """admin根据检索需求获取用户列表"""
    # current_admin只用来验证权限 不需要显式使用
    page_result = user_service.get_user_page(db, page, page_size, keywords)
    return Response.success(message="获取用列表成功", data=page_result)


@router.post("")
def create_user(
    data: UserCreateRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = user_service.create_user(db, data)
    return Response.success(message="用户创建成功", data=res)


@router.put("/{user_id}")
def update_user(
    user_id: int,
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = user_service.update_user(db, user_id, data)
    return Response.success(message="用户更新成功", data=res)


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user_service.delete_user(db, user_id, current_admin)
    return Response.success()
