"""Copy only legacy MySQL users into an empty PostgreSQL LabOps database.

The source connection is read-only. Apply requires a separately verified backup.
No legacy laboratory, equipment, or reservation table is read or copied.
"""

import argparse
import os
from pathlib import Path

import bcrypt
from sqlalchemy import MetaData, create_engine, func, select, text
from sqlalchemy.engine import make_url


def _validate(rows, target_columns):
    ids = set()
    usernames = set()
    limits = {"username": 50, "password": 255, "name": 50, "role": 50,
              "email": 50, "phone": 50, "avatar": 50}
    for row in rows:
        if row["id"] in ids or row["username"] in usernames:
            raise RuntimeError("Legacy users contain a duplicate ID or username")
        ids.add(row["id"])
        usernames.add(row["username"])
        if row["role"] not in ("admin", "student") or row["status"] not in (0, 1):
            raise RuntimeError(f"Unsupported role or status for legacy user ID {row['id']}")
        password = row["password"]
        if not isinstance(password, str) or not password.startswith(("$2a$", "$2b$", "$2y$")):
            raise RuntimeError(f"Unsupported password hash for legacy user ID {row['id']}")
        try:
            bcrypt.checkpw(b"labops-migration-format-check", password.encode("ascii"))
        except (ValueError, TypeError, UnicodeError) as exc:
            raise RuntimeError(f"Invalid bcrypt hash for legacy user ID {row['id']}") from exc
        for key, maximum in limits.items():
            value = row.get(key)
            if value is not None and len(value) > maximum:
                raise RuntimeError(f"Legacy user ID {row['id']} exceeds {key} limit")
        if not set(row).issubset(target_columns):
            raise RuntimeError("Legacy users contain columns not present in PostgreSQL")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-file", type=Path)
    parser.add_argument("--backup-restored-test-passed", action="store_true")
    args = parser.parse_args()
    source_url = os.environ.get("LABOPS_SOURCE_MYSQL_URL", "")
    target_url = os.environ.get("LABOPS_TARGET_DATABASE_URL", "")
    source = make_url(source_url) if source_url else None
    target = make_url(target_url) if target_url else None
    if not source or not source.drivername.startswith("mysql") or source.database != "lab_agent":
        parser.error("Source must be the verified legacy MySQL lab_agent database")
    if not target or not target.drivername.startswith("postgresql") or target.database != "labops":
        parser.error("Target must be the dedicated PostgreSQL labops database")
    if args.apply and (not args.backup_restored_test_passed or not args.backup_file
                       or not args.backup_file.is_file() or args.backup_file.stat().st_size == 0):
        parser.error("Apply requires the non-empty, restored-test-passed MySQL backup")

    source_engine = create_engine(source_url, pool_pre_ping=True)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    try:
        source_table = MetaData()
        source_table.reflect(source_engine, only=("users",))
        target_table = MetaData()
        target_table.reflect(target_engine, only=("users",))
        source_users = source_table.tables["users"]
        target_users = target_table.tables["users"]
        with source_engine.connect() as source_connection, target_engine.connect() as target_connection:
            source_connection.execute(text("SET SESSION TRANSACTION READ ONLY"))
            rows = [dict(row) for row in source_connection.execute(
                select(source_users).order_by(source_users.c.id)).mappings()]
            _validate(rows, set(target_users.c.keys()))
            if target_connection.execute(select(func.count()).select_from(target_users)).scalar_one() != 0:
                raise RuntimeError("Target users table is not empty; refusing to overwrite any account")
            if target_connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() not in (
                "0001_postgresql_schema", "0002_product_operations"):
                raise RuntimeError("Unexpected target Alembic revision")
            print("Verified source users:", len(rows), "IDs:", [row["id"] for row in rows])
            print("Target users: 0; source is read-only; business tables are excluded")
            if not args.apply:
                return
            with target_engine.begin() as target_transaction:
                target_transaction.execute(target_users.insert(), rows)
                target_transaction.execute(text(
                    "SELECT setval(pg_get_serial_sequence('users', 'id'), "
                    "COALESCE((SELECT max(id) FROM users), 1), EXISTS(SELECT 1 FROM users))"
                ))
                copied = target_transaction.execute(select(target_users).order_by(target_users.c.id)).mappings().all()
                for original, migrated in zip(rows, copied, strict=True):
                    for key in ("id", "username", "password", "role", "status", "name", "email", "phone", "avatar"):
                        if original[key] != migrated[key]:
                            raise RuntimeError(f"Legacy user ID {original['id']} differs in {key}")
                if len(copied) != len(rows):
                    raise RuntimeError("Copied user count differs from source")
            print("Committed users-only migration; passwords, roles, IDs, and sequence verified")
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    main()
