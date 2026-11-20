from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin, get_current_user
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.user import User
from app.services import maintenance_service

router = APIRouter(prefix="/maintenance", tags=["设备维修"])


class MaintenanceCreate(BaseModel):
    equipment_id: int = Field(gt=0)
    description: str = Field(min_length=5, max_length=2000)


class MaintenanceUpdate(BaseModel):
    status: Literal["repairing", "completed"]
    repair_notes: str | None = Field(default=None, max_length=4000)


class MaintenanceTicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipment_id: int
    equipment_name: str | None = None
    lab_name: str | None = None
    reporter_user_id: int
    reporter_name: str | None = None
    assignee_user_id: int | None
    description: str
    repair_notes: str | None
    status: str
    started_at: datetime | None
    handled_at: datetime | None
    create_time: datetime
    update_time: datetime


def _ticket_responses(db: Session, items):
    ids = {item.equipment_id for item in items}
    equipment = {row.id: row for row in db.query(Equipment).filter(Equipment.id.in_(ids)).all()} if ids else {}
    lab_ids = {row.lab_id for row in equipment.values()}
    labs = {row.id: row.name for row in db.query(Lab).filter(Lab.id.in_(lab_ids)).all()} if lab_ids else {}
    reporter_ids = {item.reporter_user_id for item in items}
    reporters = {row.id: row.name for row in db.query(User).filter(User.id.in_(reporter_ids)).all()} if reporter_ids else {}
    return [MaintenanceTicketResponse.model_validate(item).model_copy(update={
        "equipment_name": equipment[item.equipment_id].name if item.equipment_id in equipment else None,
        "lab_name": labs.get(equipment[item.equipment_id].lab_id) if item.equipment_id in equipment else None,
        "reporter_name": reporters.get(item.reporter_user_id),
    }) for item in items]


@router.get("")
def get_tickets(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = maintenance_service.list_tickets(db, user, page, page_size)
    return Response.success(data={"list": _ticket_responses(db, result["list"]),
                                  "total": result["total"]})


@router.get("/untracked")
def untracked_equipment(_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return Response.success(data=maintenance_service.list_untracked_equipment(db))


@router.post("")
def report_fault(data: MaintenanceCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = maintenance_service.create_ticket(db, user, data.equipment_id, data.description)
    return Response.success(data=_ticket_responses(db, [item])[0])


@router.put("/{ticket_id}")
def update_ticket(ticket_id: int, data: MaintenanceUpdate, admin: User = Depends(get_current_admin),
                  db: Session = Depends(get_db)):
    item = maintenance_service.update_ticket(db, admin, ticket_id, data.status, data.repair_notes)
    return Response.success(data=_ticket_responses(db, [item])[0])
