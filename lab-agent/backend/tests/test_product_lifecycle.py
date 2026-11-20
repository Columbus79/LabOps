from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.common.exceptions import BusinessException
from app.models.audit import AuditEvent
from app.models.notification import Notification
from app.models.reservation import Reservation
from app.services import maintenance_service, reservation_lifecycle
from app.services.operations_service import operations


def test_checkout_and_fault_preserve_reservation_history(db, users_and_resources):
    student, other, admin, lab, device = users_and_resources
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    current = Reservation(user_id=student.id, lab_id=lab.id, equipment_id=device.id,
                          date=today, start_time=time(0), end_time=time(23, 59),
                          status=1, review_result=1)
    db.add(current)
    db.commit()
    with pytest.raises(BusinessException, match="无权限"):
        reservation_lifecycle.check_in(db, other, current.id)
    assert reservation_lifecycle.check_in(db, student, current.id).status == 4
    assert reservation_lifecycle.check_out(db, student, current.id).status == 5
    assert current.checked_in_at and current.checked_out_at

    future = Reservation(user_id=student.id, lab_id=lab.id, equipment_id=device.id,
                         date=today + timedelta(days=1), start_time=time(10),
                         end_time=time(11), status=1, review_result=1)
    db.add(future)
    db.commit()
    ticket = maintenance_service.create_ticket(db, student, device.id, "Synthetic device fault")
    assert future.status == 7
    assert device.status == 0
    maintenance_service.update_ticket(db, admin, ticket.id, "repairing", "Investigation")
    maintenance_service.update_ticket(db, admin, ticket.id, "completed", "Fixed")
    assert device.status == 1
    assert ticket.started_at and ticket.handled_at
    assert "Investigation" in ticket.repair_notes and "Fixed" in ticket.repair_notes
    assert db.query(Notification).filter_by(user_id=student.id).count() >= 3
    assert db.query(AuditEvent).filter_by(target_type="reservation").count() >= 3

    report = operations(db, today, today + timedelta(days=1))
    assert report["reservation_total"] == 2
    assert report["approval_rate"] == 100
    assert report["repair_count"] == 1
    assert report["equipments"][0]["used_hours"] >= 0
