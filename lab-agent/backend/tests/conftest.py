import os
import tempfile
from pathlib import Path
from datetime import time

_fd, _db_path = tempfile.mkstemp(prefix="labops-test-", suffix=".sqlite3")
os.close(_fd)
Path(_db_path).unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_db_path}"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-long-enough-for-tests"
os.environ["APP_ENV"] = "testing"
os.environ["LLM_API_KEY"] = "unit-test-only-not-a-real-key"
os.environ["LLM_MODEL"] = "unit-test-model"
os.environ["LLM_BASE_URL"] = "http://127.0.0.1:9/v1"
os.environ["SILICONFLOW_EMBEDDING_API_KEY"] = "unit-test-only-not-a-real-key"

import pytest
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models.equipment import Equipment
from app.models.agent import AgentConversation, AgentMessage, ReservationConfirmation
from app.models.lab import Lab
from app.models.maintenance import MaintenanceTicket
from app.models.knowledge import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument, KnowledgeDocumentVersion
from app.models.audit import AuditEvent, AgentToolExecution
from app.models.notification import Notification
from app.models.reservation import Reservation
from app.models.user import User

CORE_TABLES = [
    User.__table__, Lab.__table__, Equipment.__table__, Reservation.__table__, Notification.__table__,
    ReservationConfirmation.__table__, MaintenanceTicket.__table__,
    AgentConversation.__table__, AgentMessage.__table__, KnowledgeDocument.__table__, KnowledgeChunk.__table__,
    AuditEvent.__table__, AgentToolExecution.__table__, KnowledgeDocumentVersion.__table__,
]


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine, tables=CORE_TABLES)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine, tables=CORE_TABLES)


@pytest.fixture
def users_and_resources(db: Session):
    student = User(username="student-one", password="unused", name="Student", role="student", status=1)
    other = User(username="student-two", password="unused", name="Other", role="student", status=1)
    admin = User(username="admin-one", password="unused", name="Admin", role="admin", status=1)
    lab = Lab(name="Research Lab", location="A-101", capacity=20,
              open_time=time(8), close_time=time(20), status=1)
    db.add_all([student, other, admin, lab])
    db.flush()
    equipment = Equipment(lab_id=lab.id, name="Microscope", quantity=1, status=1)
    db.add(equipment)
    db.commit()
    return student, other, admin, lab, equipment


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    Path(_db_path).unlink(missing_ok=True)
