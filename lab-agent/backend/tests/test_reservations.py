from datetime import date, timedelta, time

import pytest

from app.common.exceptions import BusinessException
from app.schemas.reservation import ReservationCreateRequest
from app.services import reservation_service


def request(lab_id, equipment_id=None):
    return ReservationCreateRequest(
        lab_id=lab_id, equipment_id=equipment_id,
        date=date.today() + timedelta(days=2),
        start_time=time(10), end_time=time(11),
    )


def test_reservation_conflict_and_independent_resources(db, users_and_resources):
    student, _, _, lab, equipment = users_and_resources
    reservation_service.create_reservation(db, student, request(lab.id))
    reservation_service.create_reservation(db, student, request(lab.id, equipment.id))
    with pytest.raises(BusinessException, match="该时段已被预约"):
        reservation_service.create_reservation(db, student, request(lab.id))


def test_equipment_conflict_and_cancel_releases_resource(db, users_and_resources):
    student, _, _, lab, equipment = users_and_resources
    first = reservation_service.create_reservation(db, student, request(lab.id, equipment.id))
    with pytest.raises(BusinessException, match="该时段已被预约"):
        reservation_service.create_reservation(db, student, request(lab.id, equipment.id))
    reservation_service.cancel_reservation(db, student, first.id)
    replacement = reservation_service.create_reservation(db, student, request(lab.id, equipment.id))
    assert replacement.status == 0


def test_cancel_and_audit_enforce_state_and_ownership(db, users_and_resources):
    student, other, admin, lab, _ = users_and_resources
    item = reservation_service.create_reservation(db, student, request(lab.id))
    with pytest.raises(BusinessException):
        reservation_service.cancel_reservation(db, other, item.id)
    reservation_service.audit_reservation(db, item.id, 1)
    reservation_service.cancel_reservation(db, student, item.id)
    assert item.status == 3
    with pytest.raises(BusinessException):
        reservation_service.audit_reservation(db, item.id, 2)


def test_rejected_reservations_release_the_resource(db, users_and_resources):
    student, _, _, lab, _ = users_and_resources
    first = reservation_service.create_reservation(db, student, request(lab.id))
    reservation_service.audit_reservation(db, first.id, 2)
    replacement = reservation_service.create_reservation(db, student, request(lab.id))
    assert replacement.status == 0


def test_rejects_past_time_and_out_of_hours(db, users_and_resources):
    student, _, _, lab, _ = users_and_resources
    with pytest.raises(BusinessException, match="早于当前日期"):
        reservation_service.create_reservation(db, student, ReservationCreateRequest(
            lab_id=lab.id, date=date.today() - timedelta(days=1),
            start_time=time(10), end_time=time(11),
        ))
    with pytest.raises(BusinessException, match="开放时间"):
        reservation_service.create_reservation(db, student, ReservationCreateRequest(
            lab_id=lab.id, date=date.today() + timedelta(days=2),
            start_time=time(7), end_time=time(8),
        ))
    with pytest.raises(BusinessException, match="关闭时间"):
        reservation_service.create_reservation(db, student, ReservationCreateRequest(
            lab_id=lab.id, date=date.today() + timedelta(days=2),
            start_time=time(19), end_time=time(21),
        ))


def test_time_interval_validation():
    with pytest.raises(ValueError):
        ReservationCreateRequest(
            lab_id=1, date=date.today() + timedelta(days=1),
            start_time="11:00", end_time="10:00",
        )


def test_missing_legacy_opening_hours_do_not_mean_all_day(db, users_and_resources):
    student, _, _, lab, equipment = users_and_resources
    lab.open_time = None
    lab.close_time = None
    db.commit()
    with pytest.raises(BusinessException, match="开放时间未配置"):
        reservation_service.create_reservation(db, student, request(lab.id))
    with pytest.raises(BusinessException, match="开放时间未配置"):
        reservation_service.create_reservation(db, student, request(lab.id, equipment.id))
