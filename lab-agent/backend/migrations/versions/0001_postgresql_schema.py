"""Create the initial PostgreSQL + pgvector schema.

Revision ID: 0001_postgresql_schema
Revises:
"""
from alembic import op
from sqlalchemy import inspect

from app.database import Base
import app.models

revision = "0001_postgresql_schema"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    existing_data_tables = existing - {"alembic_version"}
    if existing_data_tables:
        raise RuntimeError(
            "Refusing to initialize over existing application tables: "
            + ", ".join(sorted(existing_data_tables))
            + ". Use a fresh PostgreSQL target and the explicit migration tool."
        )
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade():
    raise RuntimeError(
        "The initial LabOps schema contains user data; automatic downgrade is disabled. "
        "Take a verified backup and write a reviewed data-preserving migration."
    )
