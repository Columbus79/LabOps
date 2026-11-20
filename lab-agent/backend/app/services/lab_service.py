from app.common.exceptions import BusinessException
from app.common.response import PageResponse
from app.models.lab import Lab
from app.models.reservation import Reservation
from app.models.user import User
from app.services import audit_service
from sqlalchemy.orm import Session
from app.schemas.lab import (
    LabCreateRequest,
    LabResponse,
    LabUpdateRequest,
)


def get_lab_page_list(
    db: Session,
    page: int,
    page_size: int,
    keywords: str | None = None,
    status: int | None = None,
):
    # select * from labs where name like "%计算机%"
    """分页式模糊查询实验室"""
    query = db.query(Lab)
    if keywords:
        query = query.filter(Lab.name.ilike(f"%{keywords}%"))
    if status is not None:
        query = query.filter(Lab.status == status)
    total = query.count()
    items = (
        query.order_by(Lab.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PageResponse(
        list=[LabResponse.model_validate(item) for item in items], total=total
    )


def get_lab(db: Session, lab_id: int):
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    return LabResponse.model_validate(lab)


def create_lab(db: Session, data: LabCreateRequest, actor: User | None = None):
    """新增"""
    exist = db.query(Lab).filter(Lab.name == data.name).first()
    if exist:
        raise BusinessException(message="实验室已经存在")
    lab = Lab(
        **data.model_dump()
    )  # {"key1": "value1", "key2": "value2"} -> key1=value1, key2=value2
    db.add(lab)
    db.flush()
    audit_service.record(db, actor, "lab.create", "lab", lab.id, {"name": lab.name})
    db.commit()
    db.refresh(lab)
    return LabResponse.model_validate(lab)


def update_lab(db: Session, lab_id: int, data: LabUpdateRequest, actor: User | None = None):
    """更新"""
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    payload = data.model_dump(
        exclude_none=True
    )  # pydantic对象转换成字典 exclude_none=True表示排除值为None的字段
    open_time = payload.get("open_time", lab.open_time)
    close_time = payload.get("close_time", lab.close_time)
    if open_time and close_time and open_time >= close_time:
        raise BusinessException("开放时间必须早于关闭时间")
    for field, value in payload.items():
        setattr(lab, field, value)
    audit_service.record(db, actor, "lab.update", "lab", lab.id, {"fields": sorted(payload)})
    db.commit()
    db.refresh(lab)
    return LabResponse.model_validate(lab)


def delete_lab(db: Session, lab_id: int, actor: User | None = None):
    """Close the lab without deleting reservation or maintenance history."""
    lab = db.query(Lab).filter(Lab.id == lab_id).with_for_update().first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    if db.query(Reservation.id).filter(Reservation.lab_id == lab_id,
                                       Reservation.status.in_((0, 1, 4))).first():
        raise BusinessException("实验室有未结束预约，请先处理预约")
    lab.status = 0
    audit_service.record(db, actor, "lab.close", "lab", lab.id)
    db.commit()
