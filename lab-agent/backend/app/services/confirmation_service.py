import hashlib
import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.database import utc_now
from app.models.agent import ReservationConfirmation
from app.models.reservation import Reservation
from app.models.user import User
from app.schemas.reservation import ReservationCreateRequest
from app.services.reservation_service import _create_reservation_in_transaction, validate_reservation_request

CONFIRMATION_TTL = timedelta(minutes=5)


def create_confirmation(db: Session, user: User, data: ReservationCreateRequest):
    raw_token = secrets.token_urlsafe(48)
    row = ReservationConfirmation(
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        user_id=user.id,
        lab_id=data.lab_id,
        equipment_id=data.equipment_id,
        date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
        remark=data.remark,
        expires_at=utc_now() + CONFIRMATION_TTL,
    )
    try:
        validate_reservation_request(db, user, data)
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return raw_token


def confirm_reservation(db: Session, user: User, raw_token: str):
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    try:
        operation = db.query(ReservationConfirmation).filter(
            ReservationConfirmation.token_hash == token_hash
        ).with_for_update().first()
        if not operation:
            raise BusinessException("预约确认凭证无效", code=404)
        if operation.user_id != user.id:
            raise BusinessException("该确认凭证不属于当前用户", code=403)
        if operation.reservation_id is not None:
            existing = db.query(Reservation).filter(Reservation.id == operation.reservation_id).first()
            if not existing:
                raise BusinessException("预约确认记录异常")
            return existing
        if operation.expires_at <= utc_now():
            raise BusinessException("预约确认已过期，请重新发起")

        data = ReservationCreateRequest(
            lab_id=operation.lab_id,
            equipment_id=operation.equipment_id,
            date=operation.date,
            start_time=operation.start_time,
            end_time=operation.end_time,
            remark=operation.remark,
        )
        reservation = _create_reservation_in_transaction(db, user, data)
        operation.used_at = utc_now()
        operation.reservation_id = reservation.id
        db.commit()
        db.refresh(reservation)
        return reservation
    except Exception:
        db.rollback()
        raise
