from datetime import date, timedelta, time

import pytest

from app.common.exceptions import BusinessException
from app.schemas.reservation import ReservationCreateRequest
from app.services.confirmation_service import confirm_reservation, create_confirmation


def test_confirmation_is_user_bound_and_idempotent(db, users_and_resources):
    student, other, _, lab, equipment = users_and_resources
    data = ReservationCreateRequest(
        lab_id=lab.id, equipment_id=equipment.id,
        date=date.today() + timedelta(days=2), start_time=time(10), end_time=time(11),
    )
    token = create_confirmation(db, student, data)
    with pytest.raises(BusinessException, match="不属于"):
        confirm_reservation(db, other, token)
    first = confirm_reservation(db, student, token)
    repeated = confirm_reservation(db, student, token)
    assert first.id == repeated.id
    assert first.status == 0
