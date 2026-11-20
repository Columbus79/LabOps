from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin, get_current_user
from app.schemas.equipment import EquipmentCreateRequest, EquipmentUpdateRequest
from app.services import equipment_service

router = APIRouter(prefix="/equipment", tags=["实验室设备信息接口"])


@router.get("/list", dependencies=[Depends(get_current_user)])
def get_equipment_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keywords: str | None = None,
    db: Session = Depends(get_db),
    lab_id: int | None = None,
):
    """admin根据keywords分页式检索数据库 获取实验室设备列表"""
    return Response.success(
        message="获取实验室设备列表成功",
        data=equipment_service.get_equipment_page(
            db, page, page_size, keywords, lab_id
        ),
    )


@router.post("")
def create_equipment(
    data: EquipmentCreateRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """admin新建实验室设备"""
    return Response.success(
        message="新增设备成功", data=equipment_service.create_equipment(db, data, admin)
    )


@router.put("/{equipment_id}")
def update_equipment(
    equipment_id: int,
    data: EquipmentUpdateRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """admin更新设备信息"""
    return Response.success(
        message="实验室设备修改成功",
        data=equipment_service.update_equipment(db, equipment_id, data, admin),
    )


@router.delete("/{equipment_id}")
def delete_equipment(equipment_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    equipment_service.delete_equipment(db, equipment_id, admin)
    return Response.success()
