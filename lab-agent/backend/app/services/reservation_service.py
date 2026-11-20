from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.common.response import PageResponse
from app.config import settings
from app.database import utc_now
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.notification import Notification
from app.models.reservation import Reservation
from app.models.user import User
from app.schemas.reservation import ReservationCreateRequest, ReservationResponse
from app.services import audit_service

BUSINESS_TZ = ZoneInfo(settings.BUSINESS_TIMEZONE)


def get_reservation_page_list(db: Session, current_user: User, page: int, page_size: int, status: int | None = None):
    query = db.query(Reservation)
    if current_user.role != "admin":
        query = query.filter(Reservation.user_id == current_user.id)
    if status is not None:
        query = query.filter(Reservation.status == status)
    total = query.count()
    items = query.order_by(Reservation.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    result = [
        ReservationResponse.model_validate(item).model_copy(update={
            "user_name": item.user.name if item.user else None,
            "lab_name": item.lab.name if item.lab else None,
            "equipment_name": item.equipment.name if item.equipment else None,
            "type": "设备" if item.equipment_id else "实验室",
        })
        for item in items
    ]
    return PageResponse(list=result, total=total)


def _validate_and_lock_resource(db: Session, data: ReservationCreateRequest):
    # Lock exactly one resource row so overlapping requests serialize without
    # coupling lab-only bookings to bookings of individual equipment.
    if data.equipment_id is None:
        resource = db.query(Lab).filter(Lab.id == data.lab_id).with_for_update().first()
        if not resource:
            raise BusinessException("实验室不存在")
        if resource.status != 1:
            raise BusinessException("实验室已关闭")
        return resource

    resource = db.query(Equipment).filter(Equipment.id == data.equipment_id).with_for_update().first()
    if not resource:
        raise BusinessException("实验室设备不存在")
    if resource.lab_id != data.lab_id:
        raise BusinessException("设备不属于所选实验室")
    if resource.status != 1:
        raise BusinessException("实验室设备正在维修")
    lab = db.query(Lab).filter(Lab.id == data.lab_id).first()
    if not lab or lab.status != 1:
        raise BusinessException("实验室不存在或已关闭")
    return lab


def validate_reservation_request(db: Session, current_user: User, data: ReservationCreateRequest):
    now = datetime.now(BUSINESS_TZ)
    local_today = now.date()
    local_time = now.time().replace(tzinfo=None, second=0, microsecond=0)
    if data.date < local_today:
        raise BusinessException("预约日期不能早于当前日期")
    if data.date == local_today and data.start_time.replace(second=0, microsecond=0) < local_time:
        raise BusinessException("当天预约开始时间不能早于当前时间")

    lab = _validate_and_lock_resource(db, data)
    if lab.open_time is None or lab.close_time is None:
        raise BusinessException("实验室开放时间未配置，暂不可预约")
    if lab.open_time and data.start_time < lab.open_time:
        raise BusinessException("预约时间不能早于实验室开放时间")
    if lab.close_time and data.end_time > lab.close_time:
        raise BusinessException("预约时间不能晚于实验室关闭时间")

    query = db.query(Reservation).filter(
        Reservation.lab_id == data.lab_id,
        Reservation.date == data.date,
        Reservation.status.in_((0, 1, 4)),
        Reservation.start_time < data.end_time,
        Reservation.end_time > data.start_time,
    )
    if data.equipment_id is None:
        query = query.filter(Reservation.equipment_id.is_(None))
    else:
        query = query.filter(Reservation.equipment_id == data.equipment_id)
    if query.first():
        raise BusinessException("该时段已被预约")


def _create_reservation_in_transaction(db: Session, current_user: User, data: ReservationCreateRequest):
    validate_reservation_request(db, current_user, data)

    reservation = Reservation(**data.model_dump(), user_id=current_user.id, status=0)
    db.add(reservation)
    db.flush()
    db.add(Notification(
        user_id=current_user.id,
        event_type="reservation_submitted",
        title="预约已提交",
        message=f"预约单 #{reservation.id} 已提交，等待管理员审核。",
    ))
    for (admin_id,) in db.query(User.id).filter(User.role == "admin").all():
        db.add(Notification(
            user_id=admin_id,
            event_type="reservation_submitted",
            title="有新的预约待审核",
            message=f"预约单 #{reservation.id} 已提交，等待审核。",
        ))
    audit_service.record(db, current_user, "reservation.submit", "reservation", reservation.id,
                         {"lab_id": data.lab_id, "equipment_id": data.equipment_id,
                          "date": data.date, "start_time": data.start_time, "end_time": data.end_time})
    return reservation


def create_reservation(db: Session, current_user: User, data: ReservationCreateRequest):
    try:
        reservation = _create_reservation_in_transaction(db, current_user, data)
        db.commit()
        db.refresh(reservation)
        return reservation
    except Exception:
        db.rollback()
        raise


def cancel_reservation(db: Session, current_user: User, reservation_id: int):
    try:
        item = db.query(Reservation).filter(Reservation.id == reservation_id).with_for_update().first()
        if not item:
            raise BusinessException("该预约记录不存在")
        if item.user_id != current_user.id:
            raise BusinessException("无权限", code=403)
        if item.status not in (0, 1):
            raise BusinessException("当前状态不可取消")
        start = datetime.combine(item.date, item.start_time, BUSINESS_TZ)
        if item.status == 1 and datetime.now(BUSINESS_TZ) >= start:
            raise BusinessException("预约开始后不能取消，请联系管理员处理异常")
        item.status = 3
        db.add(Notification(
            user_id=item.user_id,
            event_type="reservation_cancelled",
            title="预约已取消",
            message=f"预约单 #{item.id} 已取消。",
        ))
        for (admin_id,) in db.query(User.id).filter(User.role == "admin").all():
            db.add(Notification(
                user_id=admin_id,
                event_type="reservation_cancelled",
                title="预约已取消",
                message=f"预约单 #{item.id} 已取消。",
            ))
        audit_service.record(db, current_user, "reservation.cancel", "reservation", item.id)
        db.commit()
    except Exception:
        db.rollback()
        raise


def audit_reservation(db: Session, reservation_id: int, status: int, admin: User | None = None):
    if status not in (1, 2):
        raise BusinessException("审核状态错误")
    try:
        item = db.query(Reservation).filter(Reservation.id == reservation_id).with_for_update().first()
        if not item:
            raise BusinessException("预约记录不存在")
        if item.status != 0:
            raise BusinessException("当前状态不支持审核")
        if status == 1 and datetime.now(BUSINESS_TZ) >= datetime.combine(item.date, item.end_time, BUSINESS_TZ):
            raise BusinessException("预约时段已结束，不能通过")
        item.status = status
        item.reviewed_at = utc_now()
        item.review_result = status
        db.add(Notification(
            user_id=item.user_id,
            event_type="reservation_approved" if status == 1 else "reservation_rejected",
            title="预约审核结果",
            message=f"预约单 #{item.id}" + (" 已通过。" if status == 1 else " 未通过。"),
        ))
        audit_service.record(db, admin, "reservation.approve" if status == 1 else "reservation.reject",
                             "reservation", item.id)
        db.commit()
        db.refresh(item)
        return item
    except Exception:
        db.rollback()
        raise


def expire_pending_reservations():
    from app.services.reservation_lifecycle import expire_reservations
    expire_reservations()
