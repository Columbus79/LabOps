from sqlalchemy import update
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.notification import Notification
from app.models.user import User


def list_notifications(db: Session, user: User, page: int = 1, page_size: int = 20):
    query = db.query(Notification).filter(Notification.user_id == user.id)
    total = query.count()
    unread = query.filter(Notification.is_read.is_(False)).count()
    items = query.order_by(Notification.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"list": items, "total": total, "unread": unread}


def mark_read(db: Session, user: User, notification_id: int | None = None):
    query = update(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False))
    if notification_id is not None:
        query = query.where(Notification.id == notification_id)
        result = db.execute(query.values(is_read=True))
        if result.rowcount == 0 and not db.query(Notification.id).filter(
            Notification.id == notification_id, Notification.user_id == user.id
        ).first():
            raise BusinessException("通知不存在", code=404)
    else:
        db.execute(query.values(is_read=True))
    db.commit()


def unread_count(db: Session, user: User) -> int:
    return db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read.is_(False)
    ).count()
