from fastapi import APIRouter, Depends, Query
from app.database import get_db
from app.schemas.lab import (
    LabCreateRequest,
    LabUpdateRequest,
)
from app.dependencies.auth import get_current_admin, get_current_user
from app.services import lab_service
from app.common.response import Response
from sqlalchemy.orm import Session

router = APIRouter(prefix="/lab", tags=["实验室信息接口"])


@router.get("/list", dependencies=[Depends(get_current_user)])
def get_lab_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keywords: str | None = None,
    status: int | None = None,
    db: Session = Depends(get_db),
) -> Response:
    """admin根据检索需求获取实验室列表"""
    # current_admin只用来验证权限 不需要显式使用
    page_result = lab_service.get_lab_page_list(db, page, page_size, keywords, status)
    return Response.success(message="获取实验室列表成功", data=page_result)


@router.get("/{lab_id}", dependencies=[Depends(get_current_user)])
def get_lab_list(
    lab_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """admin根据检索需求获取实验室列表"""
    # current_admin只用来验证权限 不需要显式使用
    page_result = lab_service.get_lab(db, lab_id)
    return Response.success(message="获取列表成功", data=page_result)


@router.post("")
def create_lab(
    data: LabCreateRequest,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = lab_service.create_lab(db, data, current_user)
    return Response.success(message="实验室创建成功", data=res)


@router.put("/{lab_id}")
def update_lab(
    lab_id: int,
    data: LabUpdateRequest,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = lab_service.update_lab(db, lab_id, data, current_user)
    return Response.success(message="实验室更新成功", data=res)


@router.delete("/{lab_id}")
def delete_lab(
    lab_id: int,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    lab_service.delete_lab(db, lab_id, current_admin)
    return Response.success()
