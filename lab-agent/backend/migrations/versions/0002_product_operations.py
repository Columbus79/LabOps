"""Add reservation operations, audit trails, and knowledge document versions.

Revision ID: 0002_product_operations
Revises: 0001_postgresql_schema
"""
from alembic import op
from sqlalchemy import Column, DateTime, Integer, String, inspect, text

from app.database import Base
import app.models  # noqa: F401

revision = "0002_product_operations"
down_revision = "0001_postgresql_schema"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("reservations")}
    if "checked_in_at" not in columns:
        op.add_column("reservations", Column("checked_in_at", DateTime(timezone=False)))
    if "checked_out_at" not in columns:
        op.add_column("reservations", Column("checked_out_at", DateTime(timezone=False)))
    if "exception_reason" not in columns:
        op.add_column("reservations", Column("exception_reason", String(255)))
    if "reviewed_at" not in columns:
        op.add_column("reservations", Column("reviewed_at", DateTime(timezone=False)))
    if "review_result" not in columns:
        op.add_column("reservations", Column("review_result", Integer()))

    # 0001 used metadata.create_all; a fresh install may already include these
    # columns, while an existing 0001 database needs the additive changes.
    maintenance_columns = {column["name"] for column in inspect(bind).get_columns("maintenance_tickets")}
    if "started_at" not in maintenance_columns:
        op.add_column("maintenance_tickets", Column("started_at", DateTime(timezone=False)))
    knowledge_columns = {column["name"] for column in inspect(bind).get_columns("knowledge_documents")}
    if "version" not in knowledge_columns:
        op.add_column("knowledge_documents", Column("version", Integer(), nullable=False, server_default="1"))

    bind.execute(text("ALTER TABLE reservations DROP CONSTRAINT IF EXISTS ck_reservation_status"))
    bind.execute(text("ALTER TABLE reservations ADD CONSTRAINT ck_reservation_status "
                      "CHECK (status IN (0, 1, 2, 3, 4, 5, 6, 7))"))
    bind.execute(text("ALTER TABLE equipments DROP CONSTRAINT IF EXISTS ck_equipment_status"))
    bind.execute(text("ALTER TABLE equipments ADD CONSTRAINT ck_equipment_status "
                      "CHECK (status IN (0, 1, 2))"))
    Base.metadata.tables["audit_events"].create(bind=bind, checkfirst=True)
    Base.metadata.tables["agent_tool_executions"].create(bind=bind, checkfirst=True)
    Base.metadata.tables["knowledge_document_versions"].create(bind=bind, checkfirst=True)
    bind.execute(text("UPDATE reservations SET review_result = status "
                      "WHERE review_result IS NULL AND status IN (1, 2)"))
    bind.execute(text("INSERT INTO knowledge_document_versions "
                      "(document_id, version, source, content_hash, indexed_at) "
                      "SELECT document_id, version, source, content_hash, COALESCE(indexed_at, create_time) "
                      "FROM knowledge_documents WHERE status = 'indexed' "
                      "ON CONFLICT (document_id, version) DO NOTHING"))
    bind.execute(text("CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_fts ON knowledge_chunks "
                      "USING gin (to_tsvector('simple', content))"))


def downgrade():
    raise RuntimeError("Product operations contain user data; automatic downgrade is disabled")
