"""Copy only verified legacy MySQL labs and equipment into empty PostgreSQL tables.

MySQL is read-only. PostgreSQL receives both tables in one transaction, with
original IDs and fields preserved; no reservation or maintenance row is copied.
"""

import argparse
import os
from datetime import time, timedelta
from pathlib import Path

from sqlalchemy import MetaData, create_engine, func, select, text
from sqlalchemy.engine import make_url

from app.config import UPLOAD_DIR


FIELD_LIMITS = {
    "labs": {"name": 50, "location": 100, "description": 500, "img": 200},
    "equipments": {"name": 50, "description": 500, "img": 200, "spec": 100},
}


def _clock(value):
    if value is None or isinstance(value, time):
        return value
    if isinstance(value, timedelta):
        seconds = value.total_seconds()
        if seconds < 0 or seconds >= 86400 or int(seconds) != seconds:
            raise RuntimeError("Legacy opening time is outside one day")
        hour, remainder = divmod(int(seconds), 3600)
        minute, second = divmod(remainder, 60)
        return time(hour, minute, second)
    if isinstance(value, str):
        try:
            parsed = time.fromisoformat(value)
        except ValueError as exc:
            raise RuntimeError("Legacy opening time is invalid") from exc
        if parsed.tzinfo is not None:
            raise RuntimeError("Legacy opening time has a timezone")
        return parsed
    raise RuntimeError("Unsupported legacy opening time type")


def _prepare(labs, equipments, target_columns):
    lab_ids = set()
    lab_names = set()
    prepared_labs = []
    for original in labs:
        row = dict(original)
        if not set(row).issubset(target_columns["labs"]):
            raise RuntimeError("Legacy laboratory columns differ from target")
        for field in ("open_time", "close_time"):
            row[field] = _clock(row[field])
        if row["id"] in lab_ids or row["name"] in lab_names:
            raise RuntimeError("Duplicate legacy laboratory ID or name")
        if row["status"] not in (0, 1) or row["capacity"] is None or row["capacity"] < 0:
            raise RuntimeError(f"Invalid laboratory status or capacity at ID {row['id']}")
        if row["open_time"] is not None and row["close_time"] is not None and row["open_time"] >= row["close_time"]:
            raise RuntimeError(f"Invalid laboratory opening hours at ID {row['id']}")
        _check_fields("labs", row)
        lab_ids.add(row["id"])
        lab_names.add(row["name"])
        prepared_labs.append(row)

    equipment_ids = set()
    equipment_names = set()
    prepared_equipment = []
    for original in equipments:
        row = dict(original)
        if not set(row).issubset(target_columns["equipments"]):
            raise RuntimeError("Legacy equipment columns differ from target")
        pair = (row["lab_id"], row["name"])
        if row["id"] in equipment_ids or pair in equipment_names:
            raise RuntimeError("Duplicate legacy equipment ID or name within a laboratory")
        if row["lab_id"] not in lab_ids:
            raise RuntimeError(f"Orphan legacy equipment at ID {row['id']}")
        if row["status"] not in (0, 1, 2) or row["quantity"] is None or row["quantity"] <= 0:
            raise RuntimeError(f"Invalid equipment status or quantity at ID {row['id']}")
        _check_fields("equipments", row)
        equipment_ids.add(row["id"])
        equipment_names.add(pair)
        prepared_equipment.append(row)
    return prepared_labs, prepared_equipment


def _check_fields(table_name, row):
    for field, limit in FIELD_LIMITS[table_name].items():
        value = row.get(field)
        if value is not None and len(value) > limit:
            raise RuntimeError(f"{table_name} ID {row['id']} exceeds {field} limit")
    image = row.get("img")
    if image and image.startswith("/uploads/"):
        filename = Path(image).name
        if image != f"/uploads/{filename}" or not (UPLOAD_DIR / filename).is_file():
            raise RuntimeError(f"{table_name} ID {row['id']} has an unavailable image")


def _verify_copy(connection, table, expected):
    copied = [dict(row) for row in connection.execute(select(table).order_by(table.c.id)).mappings()]
    if len(copied) != len(expected):
        raise RuntimeError(f"Copied {table.name} count differs from source")
    for original, actual in zip(expected, copied, strict=True):
        for field, value in original.items():
            if actual[field] != value:
                raise RuntimeError(f"Copied {table.name} ID {original['id']} differs in {field}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-labs", type=int, required=True)
    parser.add_argument("--expected-equipments", type=int, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--source-backup", type=Path)
    parser.add_argument("--target-backup", type=Path)
    parser.add_argument("--backups-restored-test-passed", action="store_true")
    args = parser.parse_args()
    source_url = os.environ.get("LABOPS_SOURCE_MYSQL_URL", "")
    target_url = os.environ.get("LABOPS_TARGET_DATABASE_URL", "")
    source = make_url(source_url) if source_url else None
    target = make_url(target_url) if target_url else None
    if not source or not source.drivername.startswith("mysql") or source.database != "lab_agent":
        parser.error("Source must be the verified original MySQL lab_agent database")
    if not target or not target.drivername.startswith("postgresql") or target.database != "labops":
        parser.error("Target must be the formal PostgreSQL labops database")
    if args.expected_labs < 1 or args.expected_equipments < 1:
        parser.error("Positive source counts must be explicitly supplied")
    if args.apply and (not args.backups_restored_test_passed or not args.source_backup or not args.target_backup
                       or any(not path.is_file() or path.stat().st_size == 0
                              for path in (args.source_backup, args.target_backup))):
        parser.error("Apply requires non-empty source and target backups restored and verified")

    source_engine = create_engine(source_url, pool_pre_ping=True)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    try:
        source_meta = MetaData()
        source_meta.reflect(source_engine, only=("users", "labs", "equipments"))
        target_meta = MetaData()
        target_meta.reflect(target_engine, only=("users", "labs", "equipments", "reservations", "maintenance_tickets"))
        with source_engine.connect() as source_connection, target_engine.connect() as target_connection:
            source_connection.execute(text("SET SESSION TRANSACTION READ ONLY"))
            source_users = dict(source_connection.execute(select(
                source_meta.tables["users"].c.id, source_meta.tables["users"].c.username)).all())
            target_users = dict(target_connection.execute(select(
                target_meta.tables["users"].c.id, target_meta.tables["users"].c.username)).all())
            if source_users != target_users:
                raise RuntimeError("Formal users do not match the original MySQL source")
            if target_connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() != "0002_product_operations":
                raise RuntimeError("Unexpected formal Alembic revision")
            for table_name in ("labs", "equipments", "reservations", "maintenance_tickets"):
                if target_connection.execute(select(func.count()).select_from(target_meta.tables[table_name])).scalar_one():
                    raise RuntimeError(f"Formal {table_name} is not empty; refusing to overwrite")
            labs = [dict(row) for row in source_connection.execute(select(
                source_meta.tables["labs"]).order_by(source_meta.tables["labs"].c.id)).mappings()]
            equipments = [dict(row) for row in source_connection.execute(select(
                source_meta.tables["equipments"]).order_by(source_meta.tables["equipments"].c.id)).mappings()]
            if (len(labs), len(equipments)) != (args.expected_labs, args.expected_equipments):
                raise RuntimeError("Source resource counts changed after inspection")
            rows_labs, rows_equipment = _prepare(labs, equipments, {
                "labs": set(target_meta.tables["labs"].c.keys()),
                "equipments": set(target_meta.tables["equipments"].c.keys()),
            })
            print("Source MySQL resources verified:", len(rows_labs), "labs,", len(rows_equipment), "equipments")
            print("Target lab/equipment/reservation/maintenance tables: empty; original MySQL: read-only")
            if not args.apply:
                return
            # SQLAlchemy's preflight SELECTs opened a PostgreSQL transaction;
            # release its read locks before requesting an exclusive import lock.
            target_connection.rollback()
            with target_engine.begin() as transaction:
                # Prevent a concurrent application write between the preflight and insert.
                transaction.execute(text("LOCK TABLE labs, equipments, reservations, maintenance_tickets IN ACCESS EXCLUSIVE MODE"))
                for name in ("labs", "equipments", "reservations", "maintenance_tickets"):
                    if transaction.execute(select(func.count()).select_from(target_meta.tables[name])).scalar_one():
                        raise RuntimeError(f"Formal {name} changed before import")
                transaction.execute(target_meta.tables["labs"].insert(), rows_labs)
                transaction.execute(target_meta.tables["equipments"].insert(), rows_equipment)
                for name in ("labs", "equipments"):
                    transaction.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), "
                        f"COALESCE((SELECT max(id) FROM {name}), 1), EXISTS(SELECT 1 FROM {name}))"
                    ))
                _verify_copy(transaction, target_meta.tables["labs"], rows_labs)
                _verify_copy(transaction, target_meta.tables["equipments"], rows_equipment)
                if transaction.execute(select(func.count()).select_from(target_meta.tables["reservations"])).scalar_one():
                    raise RuntimeError("Reservation table unexpectedly changed during import")
            print("Committed resources-only migration; IDs, fields, foreign keys, and sequences verified")
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    main()
