from app.database import Base
from sqlalchemy.orm import Mapped, mapped_column
from datetime import time

from sqlalchemy import CheckConstraint, Integer, String, Time


class Lab(Base):
    __tablename__ = "labs"
    __table_args__ = (
        CheckConstraint("capacity >= 0", name="ck_lab_capacity_nonnegative"),
        CheckConstraint("status IN (0, 1)", name="ck_lab_status"),
        CheckConstraint("open_time IS NULL OR close_time IS NULL OR open_time < close_time", name="ck_lab_open_hours"),
    )

    name: Mapped[str] = mapped_column(String(50), unique=True, comment="实验室名称", nullable=False)
    location: Mapped[str | None] = mapped_column(String(100), comment="实验室位置")
    capacity: Mapped[int] = mapped_column(Integer, comment="容纳人数", default=0)
    open_time: Mapped[time | None] = mapped_column(Time, comment="开放开始时间")
    close_time: Mapped[time | None] = mapped_column(Time, comment="开放结束时间")
    description: Mapped[str | None] = mapped_column(String(500), comment="简介")
    img: Mapped[str | None] = mapped_column(String(200), comment="封面图")
    status: Mapped[int] = mapped_column(default=1, comment="状态: 0-关闭, 1-开放")
