"""Post-approval reservation operations and single-scheduler expiry."""
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.config import settings
from app.database import SessionLocal, utc_now
from app.models.equipment import Equipment
from app.models.notification import Notification
from app.models.reservation import Reservation
from app.models.user import User
from app.services import audit_service

BUSINESS_TZ = ZoneInfo(settings.BUSINESS_TIMEZONE)
PENDING, APPROVED, REJECTED, CANCELLED, IN_USE, COMPLETED, NO_SHOW, INTERRUPTED = range(8)


def _slot(item: Reservation):
    return (datetime.combine(item.date, item.start_time, BUSINESS_TZ),
            datetime.combine(item.date, item.end_time, BUSINESS_TZ))


def _notify(db: Session, item: Reservation, event: str, title: str, message: str):
    db.add(Notification(user_id=item.user_id, event_type=event, title=title, message=message))


def check_in(db: Session, user: User, reservation_id: int):
    try:
        item = db.query(Reservation).filter(Reservation.id == reservation_id).with_for_update().first()
        if not item:
            raise BusinessException("预约记录不存在", code=404)
        if item.user_id != user.id:
            raise BusinessException("无权限", code=403)
        if item.status != APPROVED:
            raise BusinessException("只有已通过的预约可以签到")
        now = datetime.now(BUSINESS_TZ)
        start, end = _slot(item)
        if not start <= now < end:
            raise BusinessException("只能在预约时段内签到")
        if item.equipment_id is not None:
            equipment = db.query(Equipment).filter(Equipment.id == item.equipment_id).with_for_update().first()
            if not equipment or equipment.status != 1:
                raise BusinessException("设备故障，无法签到")
        item.status = IN_USE
        item.checked_in_at = utc_now()
        _notify(db, item, "reservation_checked_in", "签到成功", f"预约单 #{item.id} 已开始使用。")
        audit_service.record(db, user, "reservation.check_in", "reservation", item.id)
        db.commit()
        db.refresh(item)
        return item
    except Exception:
        db.rollback()
        raise


def check_out(db: Session, user: User, reservation_id: int):
    try:
        item = db.query(Reservation).filter(Reservation.id == reservation_id).with_for_update().first()
        if not item:
            raise BusinessException("预约记录不存在", code=404)
        if item.user_id != user.id:
            raise BusinessException("无权限", code=403)
        if item.status != IN_USE:
            raise BusinessException("只有使用中的预约可以签退")
        item.status = COMPLETED
        item.checked_out_at = utc_now()
        _notify(db, item, "reservation_completed", "使用已完成", f"预约单 #{item.id} 已签退。")
        audit_service.record(db, user, "reservation.check_out", "reservation", item.id)
        db.commit()
        db.refresh(item)
        return item
    except Exception:
        db.rollback()
        raise


def resolve_exception(db: Session, admin: User, reservation_id: int, action: str, reason: str):
    if action not in ("complete", "interrupt") or not reason.strip():
        raise BusinessException("异常处理方式或原因无效")
    try:
        item = db.query(Reservation).filter(Reservation.id == reservation_id).with_for_update().first()
        if not item:
            raise BusinessException("预约记录不存在", code=404)
        if action == "complete" and item.status != IN_USE:
            raise BusinessException("只能结束使用中的预约")
        if action == "interrupt" and item.status not in (PENDING, APPROVED, IN_USE):
            raise BusinessException("该预约已结束，不能中断")
        item.status = COMPLETED if action == "complete" else INTERRUPTED
        item.exception_reason = reason.strip()
        if item.checked_in_at:
            item.checked_out_at = utc_now()
        _notify(db, item, "reservation_exception", "预约异常处理",
                f"预约单 #{item.id} 已由管理员处理：{reason.strip()}")
        audit_service.record(db, admin, f"reservation.{action}", "reservation", item.id,
                             {"reason": reason.strip()})
        db.commit()
        db.refresh(item)
        return item
    except Exception:
        db.rollback()
        raise


def expire_reservations():
    """Conservatively mark an unvisited slot only after its reserved end time."""
    now = datetime.now(BUSINESS_TZ)
    db = SessionLocal()
    try:
        items = db.query(Reservation).filter(
            Reservation.status.in_((PENDING, APPROVED)),
            (Reservation.date < now.date())
            | ((Reservation.date == now.date()) & (Reservation.end_time <= now.time().replace(tzinfo=None))),
        ).with_for_update(skip_locked=True).all()
        for item in items:
            if item.status == PENDING:
                item.status = CANCELLED
                item.exception_reason = "预约时段结束前未完成审核"
                event, title, action = "reservation_expired", "预约自动关闭", "reservation.expire_pending"
            else:
                item.status = NO_SHOW
                item.exception_reason = "预约时段结束前未签到"
                event, title, action = "reservation_no_show", "未签到异常", "reservation.no_show"
            _notify(db, item, event, title, f"预约单 #{item.id}：{item.exception_reason}。")
            audit_service.record(db, None, action, "reservation", item.id,
                                 {"reason": item.exception_reason})
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
