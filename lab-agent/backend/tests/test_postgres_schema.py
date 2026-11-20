from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.database import Base
from app.models.equipment import Equipment
from app.models.lab import Lab


def test_all_metadata_tables_compile_for_postgresql():
    tables = Base.metadata.sorted_tables
    assert {"users", "labs", "equipments", "reservations", "knowledge_chunks"} <= {table.name for table in tables}
    ddl = [str(CreateTable(table).compile(dialect=postgresql.dialect())) for table in tables]
    assert any("VECTOR" in statement for statement in ddl)
    assert any("DATE" in statement and "TIME" in statement for statement in ddl)


def test_resource_lock_queries_compile_to_postgresql_for_update():
    lab_query = select(Lab).where(Lab.id == 1).with_for_update()
    equipment_query = select(Equipment).where(Equipment.id == 1).with_for_update()
    assert "FOR UPDATE" in str(lab_query.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in str(equipment_query.compile(dialect=postgresql.dialect()))
