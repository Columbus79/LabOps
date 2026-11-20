from datetime import date, datetime, time

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Index, String, Time

from app.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.user import User


class Reservation(Base):

    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="ck_reservation_valid_interval"),
        CheckConstraint("status IN (0, 1, 2, 3, 4, 5, 6, 7)", name="ck_reservation_status"),
        Index("ix_reservations_resource_schedule", "lab_id", "equipment_id", "date", "status"),
        {"comment": "预约信息"},
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), comment="预约人")
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id"), comment="实验室")
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("equipments.id"), comment="设备 空表示预约实验室", nullable=True
    )
    date: Mapped[date] = mapped_column(Date, comment="预约日期", nullable=False)
    start_time: Mapped[time] = mapped_column(Time, comment="开始时间", nullable=False)
    end_time: Mapped[time] = mapped_column(Time, comment="结束时间", nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注", nullable=True)
    status: Mapped[int] = mapped_column(
        Integer, comment="0待审 1通过 2拒绝 3取消 4使用中 5完成 6未签到 7故障中断", default=0
    )
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    exception_reason: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    review_result: Mapped[int | None] = mapped_column(Integer)

    user: Mapped[User] = relationship()
    lab: Mapped[Lab] = relationship()
    equipment: Mapped[Equipment | None] = relationship()
