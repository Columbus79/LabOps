from datetime import date, timedelta, time

import pytest

from app.common.exceptions import BusinessException
from app.schemas.reservation import ReservationCreateRequest
from app.services import maintenance_service, reservation_service


def test_maintenance_blocks_bookings_and_restores_equipment(db, users_and_resources):
    student, _, admin, lab, equipment = users_and_resources
    ticket = maintenance_service.create_ticket(db, student, equipment.id, "Power switch is broken")
    assert equipment.status == 0
    with pytest.raises(BusinessException, match="维修"):
        reservation_service.create_reservation(db, student, ReservationCreateRequest(
            lab_id=lab.id, equipment_id=equipment.id,
            date=date.today() + timedelta(days=2), start_time=time(10), end_time=time(11),
        ))
    maintenance_service.update_ticket(db, admin, ticket.id, "repairing", "Replaced switch")
    assert equipment.status == 0
    maintenance_service.update_ticket(db, admin, ticket.id, "completed", "Tested successfully")
    assert equipment.status == 1
    with pytest.raises(BusinessException):
        maintenance_service.update_ticket(db, admin, ticket.id, "repairing", None)


def test_legacy_untracked_repair_state_can_be_recorded_by_admin(db, users_and_resources):
    _, _, admin, _, equipment = users_and_resources
    equipment.status = 0
    db.commit()
    assert maintenance_service.list_untracked_equipment(db) == [
        {"id": equipment.id, "name": equipment.name, "lab_name": equipment.lab.name}
    ]
    ticket = maintenance_service.create_ticket(db, admin, equipment.id, "Historical fault status confirmed")
    assert ticket.reporter_user_id == admin.id
    assert maintenance_service.list_untracked_equipment(db) == []


def test_retired_equipment_cannot_receive_repair_ticket(db, users_and_resources):
    student, _, _, _, equipment = users_and_resources
    equipment.status = 2
    db.commit()
    with pytest.raises(BusinessException, match="已停用设备"):
        maintenance_service.create_ticket(db, student, equipment.id, "Synthetic failure report")
