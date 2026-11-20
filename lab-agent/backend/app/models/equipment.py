from app.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import CheckConstraint, ForeignKey, String, Integer, UniqueConstraint

from app.models.lab import Lab


class Equipment(Base):
    __tablename__ = "equipments"
    __table_args__ = (
        UniqueConstraint("lab_id", "name", name="uq_equipment_lab_name"),
        CheckConstraint("quantity > 0", name="ck_equipment_quantity_positive"),
        CheckConstraint("status IN (0, 1, 2)", name="ck_equipment_status"),
    )

    lab_id: Mapped[int] = mapped_column(
        ForeignKey("labs.id"), comment="所属实验室", nullable=False
    )

    name: Mapped[str] = mapped_column(String(50), comment="设备名称")
    description: Mapped[str | None] = mapped_column(String(500), comment="设备说明")
    img: Mapped[str | None] = mapped_column(String(200), comment="设备图片")
    spec: Mapped[str | None] = mapped_column(String(100), comment="型号规格")
    quantity: Mapped[int] = mapped_column(Integer, comment="数量", default=1)
    status: Mapped[int] = mapped_column(Integer, comment="状态: 0-维修, 1-正常, 2-停用")

    lab: Mapped[Lab] = relationship()
