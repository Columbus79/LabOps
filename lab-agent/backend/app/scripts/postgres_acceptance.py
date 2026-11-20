"""Disposable, fixed-name PostgreSQL integration and optional live AI evaluation.

Run inside the existing backend container or CI. The source database must be
`labops`. A new `labops_acceptance` database is created only if absent and is
removed in finally; any pre-existing database with that name is left alone.
All indexed documents and users are explicitly synthetic.
"""

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
import json
import os
from pathlib import Path
import subprocess
from time import perf_counter
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


TEST_DATABASE = "labops_acceptance"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _create_isolated_database(source_url, precreated=False):
    url = make_url(source_url)
    if url.get_backend_name() != "postgresql" or url.database != "labops":
        raise RuntimeError("Acceptance requires the verified labops PostgreSQL source URL")
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            exists = connection.execute(text("SELECT 1 FROM pg_database WHERE datname=:name"),
                                        {"name": TEST_DATABASE}).first()
            if precreated:
                if not exists:
                    raise RuntimeError("Precreated acceptance database is missing")
            elif exists:
                raise RuntimeError("Existing labops_acceptance database will not be overwritten")
            else:
                connection.execute(text(f"CREATE DATABASE {TEST_DATABASE}"))
        test_url = url.set(database=TEST_DATABASE)
        if precreated:
            target = create_engine(test_url)
            try:
                with target.connect() as connection:
                    marker = connection.execute(text(
                        "SELECT marker FROM acceptance_control.labops_acceptance_marker"
                    )).scalar_one()
                    other_tables = connection.execute(text(
                        "SELECT count(*) FROM pg_tables WHERE schemaname='public'"
                    )).scalar_one()
                    if marker != "LabOps synthetic acceptance database v1" or other_tables:
                        raise RuntimeError("Precreated database is not an empty marked test database")
            finally:
                target.dispose()
            admin.dispose()
            return None, test_url
        return admin, test_url
    except Exception:
        admin.dispose()
        raise


def _drop_created_database(admin):
    # Only called when _create_isolated_database created this database in this run.
    try:
        with admin.connect() as connection:
            connection.execute(text(f"DROP DATABASE {TEST_DATABASE} WITH (FORCE)"))
    finally:
        admin.dispose()


def _migrate(test_url):
    env = os.environ.copy()
    env["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
    env["APP_ENV"] = "testing"
    env.pop("LABOPS_TARGET_DATABASE_URL", None)
    result = subprocess.run(["alembic", "upgrade", "head"], cwd=FIXTURES.parents[1],
                            env=env, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"Alembic test migration failed (exit {result.returncode})")


def _run_integration():
    from app.config import settings
    from app.common.exceptions import BusinessException
    from app.database import SessionLocal
    from app.models.equipment import Equipment
    from app.models.lab import Lab
    from app.models.maintenance import MaintenanceTicket
    from app.models.reservation import Reservation
    from app.models.user import User
    from app.schemas.reservation import ReservationCreateRequest
    from app.services import confirmation_service, maintenance_service, reservation_service

    db = SessionLocal()
    try:
        version = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version == "0002_product_operations"
        student = User(username="SYNTH-student", password="synthetic-no-login",
                       name="SYNTH Student", role="student", status=1)
        other = User(username="SYNTH-other", password="synthetic-no-login",
                     name="SYNTH Other", role="student", status=1)
        admin = User(username="SYNTH-admin", password="synthetic-no-login",
                     name="SYNTH Admin", role="admin", status=1)
        lab = Lab(name="SYNTH-A", location="SYNTH-only", capacity=5,
                  open_time=time(8), close_time=time(20), status=1)
        db.add_all([student, other, admin, lab])
        db.flush()
        equipment = Equipment(lab_id=lab.id, name="SYNTH-Microscope", quantity=1, status=1)
        db.add(equipment)
        db.commit()

        tomorrow = datetime.now(ZoneInfo(settings.BUSINESS_TIMEZONE)).date() + timedelta(days=1)
        slot = ReservationCreateRequest(lab_id=lab.id, date=tomorrow,
                                        start_time=time(10), end_time=time(11))

        def compete(user_id):
            worker = SessionLocal()
            try:
                user = worker.get(User, user_id)
                try:
                    return ("success", reservation_service.create_reservation(worker, user, slot).id)
                except BusinessException as exc:
                    return ("rejected", exc.message)
            finally:
                worker.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(compete, (student.id, other.id)))
        assert sorted(kind for kind, _ in outcomes) == ["rejected", "success"], outcomes
        assert db.query(Reservation).count() == 1

        confirmation_slot = ReservationCreateRequest(
            lab_id=lab.id, date=tomorrow, start_time=time(12), end_time=time(13))
        token = confirmation_service.create_confirmation(db, student, confirmation_slot)
        try:
            confirmation_service.confirm_reservation(db, other, token)
            raise AssertionError("Cross-user confirmation was accepted")
        except BusinessException as exc:
            assert exc.code == 403
        first = confirmation_service.confirm_reservation(db, student, token)
        again = confirmation_service.confirm_reservation(db, student, token)
        assert first.id == again.id and db.query(Reservation).count() == 2
        assert reservation_service.get_reservation_page_list(db, other, 1, 20).total <= 1

        equipment_slot = ReservationCreateRequest(
            lab_id=lab.id, equipment_id=equipment.id, date=tomorrow,
            start_time=time(14), end_time=time(15))
        affected = reservation_service.create_reservation(db, student, equipment_slot)
        reservation_service.audit_reservation(db, affected.id, 1, admin)
        ticket = maintenance_service.create_ticket(db, student, equipment.id,
                                                   "SYNTH broken power button")
        assert db.get(Reservation, affected.id).status == 7
        assert db.get(Equipment, equipment.id).status == 0
        maintenance_service.update_ticket(db, admin, ticket.id, "repairing", "SYNTH repair")
        maintenance_service.update_ticket(db, admin, ticket.id, "completed", "SYNTH tested")
        assert db.get(Equipment, equipment.id).status == 1
        assert db.get(MaintenanceTicket, ticket.id).status == "completed"

        return {"alembic_revision": version, "concurrent_requests": 2,
                "concurrent_successes": 1, "confirmation_idempotent": True,
                "cross_user_confirmation_blocked": True,
                "fault_interrupts_booking": True, "repair_restores_equipment": True,
                "lab_id": lab.id, "equipment_id": equipment.id,
                "student_id": student.id, "admin_id": admin.id}
    finally:
        db.close()


async def _evaluate_agent(db, cases, resources):
    from app.models.reservation import Reservation
    from app.models.user import User
    from app.schemas.ai import ChatMessage, ChatRequest
    from app.services.agent_service import stream_agent

    rows = []
    for case in cases:
        user = db.get(User, resources[case["role"] + "_id"])
        prompt = case["prompt"].format(**resources)
        before = db.query(Reservation).count()
        started = perf_counter()
        request = ChatRequest(messages=[ChatMessage(role="user", content=prompt)])
        events = [event async for event in stream_agent(db, user, request,
                                                        trace_id=f"SYNTH-{case['id']}")]
        tool_names = [event["name"] for event in events if event["type"] == "tool_start"]
        previews = [event for event in events if event["type"] == "reservation_preview"]
        errors = [event["message"] for event in events if event["type"] == "error"]
        after = db.query(Reservation).count()
        completed = not errors
        rows.append({"id": case["id"], "tools": tool_names,
                     "tool_match": set(case["expected_tools"]).issubset(tool_names) if completed else None,
                     "preview_match": bool(previews) == case["expect_preview"] if completed else None,
                     "unexpected_reservation_writes": after - before,
                     "error_type": ("rate_limit" if "限流" in errors[0] else "model_or_tool_error")
                     if errors else None,
                     "latency_ms": round((perf_counter() - started) * 1000, 2)})
    completed_rows = [row for row in rows if row["error_type"] is None]
    return {"cases": rows,
            "completed_cases": len(completed_rows),
            "errored_cases": len(rows) - len(completed_rows),
            "tool_match_rate": sum(row["tool_match"] for row in completed_rows) / len(completed_rows)
            if completed_rows else None,
            "preview_match_rate": sum(row["preview_match"] for row in completed_rows) / len(completed_rows)
            if completed_rows else None,
            "unexpected_reservation_writes": sum(row["unexpected_reservation_writes"] for row in rows)}


def _run_live_ai(resources):
    from app.database import SessionLocal
    from app.models.knowledge import KnowledgeChunk
    from app.services import kb_service

    db = SessionLocal()
    try:
        indexed = kb_service.index_markdown_documents(db, FIXTURES / "synthetic_kb")
        statuses = {item["status"] for item in indexed["documents"]}
        if statuses != {"indexed"}:
            raise RuntimeError(f"Synthetic document indexing incomplete: {sorted(statuses)}")
        cases = json.loads((FIXTURES / "rag_eval_synthetic_1_1.json").read_text())
        rag = kb_service.evaluate_retrieval(db, cases, top_k=5)
        dimensions = sorted({dimension for (dimension,) in db.query(KnowledgeChunk.embedding_dimension).distinct()})
        assert dimensions == [4096], dimensions
        agent_cases = json.loads((FIXTURES / "agent_eval_synthetic_1_0.json").read_text())
        agent = asyncio.run(_evaluate_agent(db, agent_cases, resources))
        return {"rag": {"indexed_documents": len(indexed["documents"]),
                        "vector_dimensions": dimensions, **rag}, "agent": agent}
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-ai", action="store_true", help="Call configured LLM and Embedding APIs using only synthetic text")
    parser.add_argument("--precreated", action="store_true", help="Use a marked, empty test database created by an administrator")
    args = parser.parse_args()
    source_url = os.environ.get("DATABASE_URL", "")
    admin, test_url = _create_isolated_database(source_url, args.precreated)
    try:
        _migrate(test_url)
        os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
        os.environ["APP_ENV"] = "testing"
        from app.database import engine
        resources = _run_integration()
        result = {"database": TEST_DATABASE, "integration": {
            key: value for key, value in resources.items() if key not in {"lab_id", "equipment_id", "student_id", "admin_id"}
        }}
        if args.live_ai:
            result.update(_run_live_ai(resources))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        if "engine" in locals():
            engine.dispose()
        if admin is not None:
            _drop_created_database(admin)


if __name__ == "__main__":
    main()
