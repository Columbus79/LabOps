from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import exists
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.database import utc_now
from app.config import settings
from app.models.equipment import Equipment
from app.models.maintenance import MaintenanceTicket
from app.models.notification import Notification
from app.models.reservation import Reservation
from app.models.user import User
from app.services import audit_service


def create_ticket(db: Session, user: User, equipment_id: int, description: str):
    try:
        equipment = db.query(Equipment).filter(Equipment.id == equipment_id).with_for_update().first()
        if not equipment:
            raise BusinessException("设备不存在", code=404)
        if equipment.status == 2:
            raise BusinessException("已停用设备不能申报维修，请管理员先核实设备状态")
        active = db.query(MaintenanceTicket).filter(
            MaintenanceTicket.equipment_id == equipment_id,
            MaintenanceTicket.status.in_(("reported", "repairing")),
        ).first()
        if active:
            raise BusinessException("该设备已有未完成的维修工单")
        equipment.status = 0
        ticket = MaintenanceTicket(
            equipment_id=equipment.id,
            reporter_user_id=user.id,
            description=description,
            status="reported",
        )
        db.add(ticket)
        db.flush()
        today = datetime.now(ZoneInfo(settings.BUSINESS_TIMEZONE)).date()
        affected = db.query(Reservation).filter(
            Reservation.equipment_id == equipment.id,
            Reservation.date >= today,
            Reservation.status.in_((0, 1, 4)),
        ).with_for_update().all()
        for reservation in affected:
            reservation.status = 7
            reservation.exception_reason = f"设备故障，关联维修工单 #{ticket.id}"
            if reservation.checked_in_at:
                reservation.checked_out_at = utc_now()
            db.add(Notification(
                user_id=reservation.user_id,
                event_type="reservation_interrupted",
                title="设备故障影响预约",
                message=f"预约单 #{reservation.id} 因设备故障中断，请联系管理员。",
            ))
            audit_service.record(db, user, "reservation.interrupt_fault", "reservation", reservation.id,
                                 {"maintenance_ticket_id": ticket.id})
        db.add(Notification(
            user_id=user.id,
            event_type="maintenance_reported",
            title="故障申报已登记",
            message=f"设备 {equipment.name} 的维修工单 #{ticket.id} 已创建。",
        ))
        for (admin_id,) in db.query(User.id).filter(User.role == "admin").all():
            db.add(Notification(
                user_id=admin_id,
                event_type="maintenance_reported",
                title="收到新的设备故障申报",
                message=f"设备 {equipment.name} 的维修工单 #{ticket.id} 待处理。",
            ))
        audit_service.record(db, user, "maintenance.report", "maintenance_ticket", ticket.id,
                             {"equipment_id": equipment.id, "affected_reservations": len(affected)})
        db.commit()
        db.refresh(ticket)
        return ticket
    except Exception:
        db.rollback()
        raise


def list_tickets(db: Session, user: User, page: int, page_size: int):
    query = db.query(MaintenanceTicket)
    if user.role != "admin":
        query = query.filter(MaintenanceTicket.reporter_user_id == user.id)
    total = query.count()
    items = query.order_by(MaintenanceTicket.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"list": items, "total": total}


def list_untracked_equipment(db: Session):
    """Find unavailable equipment with no active ticket, including legacy states."""
    active = exists().where(
        MaintenanceTicket.equipment_id == Equipment.id,
        MaintenanceTicket.status.in_(("reported", "repairing")),
    )
    items = db.query(Equipment).filter(Equipment.status == 0, ~active).order_by(Equipment.id).all()
    return [{"id": item.id, "name": item.name, "lab_name": item.lab.name} for item in items]


def get_equipment_status(db: Session, equipment_id: int):
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise BusinessException("设备不存在", code=404)
    active = db.query(MaintenanceTicket).filter(
        MaintenanceTicket.equipment_id == equipment_id,
        MaintenanceTicket.status.in_(("reported", "repairing")),
    ).order_by(MaintenanceTicket.id.desc()).first()
    return {"equipment_id": equipment.id, "name": equipment.name,
            "status": equipment.status,
            "active_ticket": {"id": active.id, "status": active.status} if active else None}


def update_ticket(db: Session, admin: User, ticket_id: int, status: str, repair_notes: str | None):
    try:
        ticket = db.query(MaintenanceTicket).filter(MaintenanceTicket.id == ticket_id).with_for_update().first()
        if not ticket:
            raise BusinessException("维修工单不存在", code=404)
        allowed = {"reported": {"repairing"}, "repairing": {"completed"}}
        if status not in allowed.get(ticket.status, set()):
            raise BusinessException("维修工单状态流转无效")
        equipment = db.query(Equipment).filter(Equipment.id == ticket.equipment_id).with_for_update().first()
        ticket.status = status
        ticket.assignee_user_id = admin.id
        if repair_notes:
            ticket.repair_notes = (ticket.repair_notes + "\n" if ticket.repair_notes else "") + repair_notes
        ticket.started_at = utc_now() if status == "repairing" else ticket.started_at
        ticket.handled_at = utc_now() if status == "completed" else ticket.handled_at
        if status == "completed":
            other_active = db.query(MaintenanceTicket.id).filter(
                MaintenanceTicket.equipment_id == equipment.id,
                MaintenanceTicket.id != ticket.id,
                MaintenanceTicket.status.in_(("reported", "repairing")),
            ).first()
            if not other_active:
                equipment.status = 1
        db.add(Notification(
            user_id=ticket.reporter_user_id,
            event_type=f"maintenance_{status}",
            title="维修工单状态更新",
            message=f"工单 #{ticket.id} 状态已更新为 {status}。",
        ))
        audit_service.record(db, admin, f"maintenance.{status}", "maintenance_ticket", ticket.id,
                             {"equipment_id": equipment.id})
        db.commit()
        db.refresh(ticket)
        return ticket
    except Exception:
        db.rollback()
        raise
