from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.audit import AuditEvent

router = APIRouter(prefix="/audit", tags=["业务审计"])


@router.get("")
def list_audit(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
               _admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    query = db.query(AuditEvent)
    items = query.order_by(AuditEvent.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return Response.success(data={"total": query.count(), "list": [
        {"id": item.id, "actor_username": item.actor_username, "action": item.action,
         "target_type": item.target_type, "target_id": item.target_id,
         "detail": item.detail, "create_time": item.create_time}
        for item in items
    ]})
