import json

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.user import User


def record(db: Session, actor: User | None, action: str, target_type: str,
           target_id: int, detail: dict | None = None):
    """Append to the same transaction as the business change; never store secrets."""
    db.add(AuditEvent(
        actor_user_id=actor.id if actor else None,
        actor_username=actor.username if actor else "scheduler",
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=json.dumps(detail or {}, ensure_ascii=False, default=str),
    ))
