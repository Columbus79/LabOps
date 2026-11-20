from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["站内通知"])


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    event_type: str
    title: str
    message: str
    is_read: bool
    create_time: datetime


@router.get("")
def get_notifications(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                     current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = notification_service.list_notifications(db, current_user, page, page_size)
    return Response.success(data={"list": [NotificationResponse.model_validate(item) for item in result["list"]],
                                  "total": result["total"], "unread": result["unread"]})


@router.get("/unread-count")
def get_unread_count(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return Response.success(data={"count": notification_service.unread_count(db, current_user)})


@router.put("/{notification_id}/read")
def mark_notification_read(notification_id: int, current_user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    notification_service.mark_read(db, current_user, notification_id)
    return Response.success()


@router.put("/read-all")
def mark_all_notifications_read(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notification_service.mark_read(db, current_user)
    return Response.success()
