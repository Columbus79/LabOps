from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin, get_current_user
from app.models.user import User
from app.schemas.reservation import ReservationCreateRequest, ReservationResponse, AuditReservationRequest, ReservationExceptionRequest
from app.services import reservation_lifecycle, reservation_service

router = APIRouter(prefix="/reservation", tags=["预约相关的接口"])


@router.get("/list")
def get_reservation_page_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: int | None = Query(default=None, ge=0, le=7),
):
    """分页查询预约记录"""

    page_res = reservation_service.get_reservation_page_list(
        db, current_user, page, page_size, status
    )
    return Response.success(data=page_res)


@router.post("")
def create_reservation(
    data: ReservationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建预约记录并写入 reservations 表"""

    reservation_service.create_reservation(db, current_user, data)
    return Response.success()


@router.put("/{reservation_id}/cancel")
def cancel_reservation(
    reservation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """学生取消预约"""

    reservation_service.cancel_reservation(db, current_user, reservation_id)
    return Response.success()


@router.put("/{reservation_id}/audit")
def audit_reservation(
    reservation_id: int,
    data: AuditReservationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """管理员审核预约"""

    reservation_service.audit_reservation(db, reservation_id, data.status, current_user)
    return Response.success()


@router.put("/{reservation_id}/check-in")
def check_in(reservation_id: int, current_user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    item = reservation_lifecycle.check_in(db, current_user, reservation_id)
    return Response.success(data=ReservationResponse.model_validate(item))


@router.put("/{reservation_id}/check-out")
def check_out(reservation_id: int, current_user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    item = reservation_lifecycle.check_out(db, current_user, reservation_id)
    return Response.success(data=ReservationResponse.model_validate(item))


@router.put("/{reservation_id}/resolve")
def resolve_exception(reservation_id: int, data: ReservationExceptionRequest,
                      admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    item = reservation_lifecycle.resolve_exception(db, admin, reservation_id, data.action, data.reason)
    return Response.success(data={"id": item.id, "status": item.status,
                                  "exception_reason": item.exception_reason})

