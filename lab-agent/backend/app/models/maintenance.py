from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MaintenanceTicket(Base):
    __tablename__ = "maintenance_tickets"
    __table_args__ = (
        CheckConstraint("status IN ('reported', 'repairing', 'completed')", name="ck_maintenance_status"),
        Index("ix_maintenance_equipment_status", "equipment_id", "status"),
    )

    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipments.id"), nullable=False)
    reporter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assignee_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    repair_notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="reported")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
