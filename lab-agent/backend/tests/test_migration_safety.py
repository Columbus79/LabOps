"""Users-only migration rejects malformed or unsafe legacy account rows."""
import bcrypt
import pytest

from app.scripts.migrate_mysql_users import _validate


def _row(**changes):
    row = {
        "id": 1,
        "username": "legacy_admin",
        "password": bcrypt.hashpw(b"synthetic-test-password", bcrypt.gensalt(rounds=4)).decode(),
        "name": "Legacy Admin",
        "role": "admin",
        "status": 1,
        "email": None,
        "phone": None,
        "avatar": None,
    }
    row.update(changes)
    return row


def test_valid_legacy_user_is_accepted():
    row = _row()
    _validate([row], set(row))


@pytest.mark.parametrize("change", [
    {"role": "superuser"},
    {"status": 3},
    {"password": "plaintext"},
    {"username": "x" * 51},
])
def test_invalid_legacy_user_is_rejected(change):
    row = _row(**change)
    with pytest.raises(RuntimeError):
        _validate([row], set(row))


def test_duplicate_user_id_is_rejected():
    first = _row()
    second = _row(username="other")
    with pytest.raises(RuntimeError, match="duplicate"):
        _validate([first, second], set(first))
