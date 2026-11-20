from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.common.response import PageResponse
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.maintenance import MaintenanceTicket
from app.models.reservation import Reservation
from app.models.user import User
from app.services import audit_service
from app.schemas.equipment import (
    EquipmentCreateRequest,
    EquipmentResponse,
    EquipmentUpdateRequest,
)


def get_equipment_page(
    db: Session,
    page: int,
    page_size: int,
    keywords: str | None = None,
    lab_id: int | None = None,
):
    # select * from equipments where name like "%keywords%"
    """分页式模糊查询实验室设备"""
    query = db.query(Equipment)
    if lab_id is not None:
        query = query.filter(Equipment.lab_id == lab_id)
    if keywords:
        query = query.filter(Equipment.name.ilike(f"%{keywords}%"))
    total = query.count()
    items = (
        query.order_by(Equipment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    result = []
    if items:
        for item in items:
            res = EquipmentResponse(
                id=item.id,
                lab_id=item.lab_id,
                lab_name=item.lab.name,
                name=item.name,
                description=item.description,
                img=item.img,
                spec=item.spec,
                quantity=item.quantity,
                status=item.status,
            )
            result.append(res)
    return PageResponse(list=result, total=total)


def create_equipment(db: Session, data: EquipmentCreateRequest, actor: User | None = None):
    """新增"""
    lab = db.query(Lab).filter(Lab.id == data.lab_id).first()
    if not lab:
        raise BusinessException(message="该实验室不存在存在")
    exist = (
        db.query(Equipment)
        .filter(Equipment.lab_id == data.lab_id, Equipment.name == data.name)
        .first()
    )
    if exist:
        raise BusinessException(message="该实验室下已经存在该名称的设备了")
    if data.status != 1:
        raise BusinessException("新设备必须为正常状态，故障须通过维修工单登记")

    equipment = Equipment(**data.model_dump())
    db.add(equipment)
    db.flush()
    audit_service.record(db, actor, "equipment.create", "equipment", equipment.id,
                         {"lab_id": equipment.lab_id, "name": equipment.name})
    db.commit()
    db.refresh(equipment)
    res = EquipmentResponse(
        id = equipment.id,
        **data.model_dump(),
        lab_name = lab.name
    )
    return res


def update_equipment(
    db: Session,
    equipment_id: int,
    data: EquipmentUpdateRequest,
    actor: User | None = None,
):
    """更新"""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise BusinessException(message="设备不存在")
    payload = data.model_dump(exclude_none=True)
    lab_id = payload.get("lab_id", equipment.lab_id)
    name = payload.get("name", equipment.name)
    if not db.query(Lab).filter(Lab.id == lab_id).first():
        raise BusinessException(message="实验室不存在")
    exist = (
        db.query(Equipment)
        .filter(
            Equipment.lab_id == lab_id,
            Equipment.name == name,
            Equipment.id != equipment.id,
        )
        .first()
    )
    # 查询本质上就是拿着你手里有的信息去数据库里面匹配, 这里翻译过来就是:
    # 我现在要避免这个更新重名 所以我尝试去数据库里面找一个equipment
    # 如果这个equipment满足如下条件 我就判定你这次更新会创造一个重名的equipment
    # 我手里拿着的name跟lab_id实际上就是最终写入的信息
    # lab_id可能会是一个不存在的实验室 name可能会是一个目标实验室中已经存在的设备名称 所以我们这里排查 要是同一个实验室内出现了同一个名称的设备 我们就要制裁 不要写入实验室中
    # 而且我现在对这个filter()中的Equipment这个有理解了 这里的Equipment未来是一个equipment item我们现在在筛选用这个存在于未来的Equipment的各个属性对比我们手里的筛选信息(这里是最终写入信息)从而拿到符合要求的equipment
    # 但是GPT说不对 但实际上我认为没有什么区别

    if exist:
        raise BusinessException(message="同一个实验室内不能存在同名的设备")

    if payload.get("status") == 0 and equipment.status != 0:
        raise BusinessException("维修状态必须由故障工单设置")
    if payload.get("status") in (1, 2) and db.query(MaintenanceTicket.id).filter(
        MaintenanceTicket.equipment_id == equipment_id,
        MaintenanceTicket.status.in_(("reported", "repairing")),
    ).first():
        raise BusinessException("设备有未完成维修工单，不能直接更改状态")

    for field, value in payload.items():
        setattr(equipment, field, value)
    audit_service.record(db, actor, "equipment.update", "equipment", equipment.id,
                         {"fields": sorted(payload)})
    db.commit()
    db.refresh(equipment)
    res = EquipmentResponse(
        id=equipment.id, lab_id=equipment.lab_id, name=equipment.name,
        description=equipment.description, img=equipment.img, spec=equipment.spec,
        quantity=equipment.quantity, status=equipment.status,
        lab_name=db.query(Lab).filter(Lab.id == equipment.lab_id).first().name,
    )
    return res


def delete_equipment(db: Session, equipment_id: int, actor: User | None = None):
    """Retire a device while preserving its maintenance and booking history."""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).with_for_update().first()
    if not equipment:
        raise BusinessException(message="该设备不存在")
    if db.query(Reservation.id).filter(Reservation.equipment_id == equipment_id,
                                       Reservation.status.in_((0, 1, 4))).first():
        raise BusinessException("设备有未结束预约，请先处理预约")
    if db.query(MaintenanceTicket.id).filter(MaintenanceTicket.equipment_id == equipment_id,
                                             MaintenanceTicket.status.in_(("reported", "repairing"))).first():
        raise BusinessException("设备有未完成维修工单")
    equipment.status = 2
    audit_service.record(db, actor, "equipment.retire", "equipment", equipment.id)
    db.commit()
