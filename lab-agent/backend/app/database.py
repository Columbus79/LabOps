from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import settings

engine_options = {"pool_pre_ping": True, "pool_recycle": 1800}
if settings.DATABASE_URL.startswith(("postgresql", "mysql")):
    engine_options.update(pool_size=5, max_overflow=10)
if settings.DATABASE_URL.startswith(("postgresql://", "postgresql+psycopg://")):
    engine_options["connect_args"] = {"options": "-c timezone=UTC"}
engine = create_engine(settings.DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, sort_order=-1)
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now(), onupdate=func.now()
    )
