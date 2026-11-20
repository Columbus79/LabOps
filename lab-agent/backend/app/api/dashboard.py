from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin, get_current_user
from app.config import settings
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.reservation import Reservation
from app.services.operations_service import operations

router = APIRouter(prefix="/dashboard", tags=["首页统计"])


@router.get("/summary")
def summary(_user=Depends(get_current_user), db: Session = Depends(get_db)):
    data = {
        "labs_total": db.query(Lab).count(),
        "labs_open": db.query(Lab).filter(Lab.status == 1).count(),
        "equipment_normal": db.query(Equipment).filter(Equipment.status == 1).count(),
        "equipment_maintenance": db.query(Equipment).filter(Equipment.status == 0).count(),
        "reservations_pending": db.query(Reservation).filter(Reservation.status == 0).count(),
        "reservations_approved": db.query(Reservation).filter(Reservation.status.in_((1, 4, 5))).count(),
        "reservations_in_use": db.query(Reservation).filter(Reservation.status == 4).count(),
        "equipment_retired": db.query(Equipment).filter(Equipment.status == 2).count(),
    }
    return Response.success(data=data)


@router.get("/operations")
def operations_report(start: date | None = None, end: date | None = None,
                      _admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    today = datetime.now(ZoneInfo(settings.BUSINESS_TIMEZONE)).date()
    actual_end = end or today
    actual_start = start or actual_end - timedelta(days=29)
    return Response.success(data=operations(db, actual_start, actual_end))
