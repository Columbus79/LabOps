from datetime import datetime
import json
import logging
from zoneinfo import ZoneInfo

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.config import settings
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.user import User
from app.schemas.reservation import ReservationCreateRequest
from app.services import (confirmation_service, equipment_service, kb_service, lab_service,
                          maintenance_service, reservation_service)
from app.services.operations_service import operations

logger = logging.getLogger("labops.agent.tools")


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def build_tools(db: Session, current_user: User):
    @tool
    def search_lab_docs(query: str) -> str:
        """从实验室规则文档中检索预约、安全和开放时间要求。"""
        try:
            return kb_service.search(db, query) or "没有检索到相关的资料"
        except Exception:
            logger.exception("Knowledge search tool failed")
            return "知识库暂时不可用。"

    @tool
    def list_open_labs(keywords: str = "") -> str:
        """查询当前开放的实验室，返回真实数据库中的实验室信息。"""
        try:
            page = lab_service.get_lab_page_list(
                db, page=1, page_size=10, keywords=keywords.strip() or None, status=1
            )
            rows = [{
                "id": item.id, "name": item.name, "location": item.location,
                "capacity": item.capacity, "open_time": item.open_time,
                "close_time": item.close_time,
                "reservable": item.open_time is not None and item.close_time is not None,
            } for item in page.list]
            return _json({"total": page.total, "labs": rows})
        except Exception:
            logger.exception("Lab lookup tool failed")
            return _json({"ok": False, "error": "实验室查询暂时不可用"})

    @tool
    def list_lab_equipments(lab_id: int, keywords: str = "") -> str:
        """查询指定实验室中的设备及设备状态。"""
        try:
            page = equipment_service.get_equipment_page(
                db, page=1, page_size=20, keywords=keywords.strip() or None, lab_id=lab_id
            )
            rows = [{
                "id": item.id, "name": item.name, "lab_id": item.lab_id,
                "lab_name": item.lab_name, "spec": item.spec,
                "quantity": item.quantity, "status": item.status,
            } for item in page.list]
            return _json({"total": page.total, "equipments": rows})
        except Exception:
            logger.exception("Equipment lookup tool failed")
            return _json({"ok": False, "error": "设备查询暂时不可用"})

    @tool
    def list_reservations(status: int | None = None) -> str:
        """查询当前用户可访问的预约；学生仅能查看自己的预约。"""
        try:
            page = reservation_service.get_reservation_page_list(db, current_user, 1, 10, status)
            return _json({"total": page.total, "reservations": [
                {"id": row.id, "lab_name": row.lab_name, "equipment_name": row.equipment_name,
                 "date": row.date, "start_time": row.start_time, "end_time": row.end_time,
                 "status": row.status} for row in page.list
            ]})
        except Exception:
            logger.exception("Reservation lookup tool failed")
            return _json({"ok": False, "error": "预约查询暂时不可用"})

    @tool
    def get_equipment_maintenance(equipment_id: int) -> str:
        """查询设备的当前维修状态与未完成工单，不返回其他用户的隐私。"""
        try:
            return _json(maintenance_service.get_equipment_status(db, equipment_id))
        except BusinessException as exc:
            return _json({"ok": False, "error": exc.message})
        except Exception:
            logger.exception("Maintenance lookup tool failed")
            return _json({"ok": False, "error": "设备状态查询暂时不可用"})

    @tool
    def get_operations_stats() -> str:
        """管理员查询最近30天真实数据库中的预约、利用率和维修统计。"""
        if current_user.role != "admin":
            return _json({"ok": False, "error": "仅管理员可以查看运营统计"})
        today = datetime.now(ZoneInfo(settings.BUSINESS_TIMEZONE)).date()
        from datetime import timedelta
        report = operations(db, today - timedelta(days=29), today)
        return _json({
            "reservation_total": report["reservation_total"],
            "approval_rate": report["approval_rate"],
            "repair_count": report["repair_count"],
            "average_repair_hours": report["average_repair_hours"],
            "labs": report["labs"], "equipments": report["equipments"],
        })

    @tool
    def create_lab_reservation(
        lab_id: int,
        date: str,
        start_time: str,
        end_time: str,
        equipment_id: int | None = None,
        remark: str | None = None,
    ) -> str:
        """生成预约预览和一次性确认凭证；此工具不会提交真实预约。"""
        try:
            data = ReservationCreateRequest(
                lab_id=lab_id, equipment_id=equipment_id, date=date,
                start_time=start_time, end_time=end_time, remark=remark,
            )
            token = confirmation_service.create_confirmation(db, current_user, data)
            lab = db.query(Lab).filter(Lab.id == lab_id).first()
            equipment = (
                db.query(Equipment).filter(Equipment.id == equipment_id).first()
                if equipment_id is not None else None
            )
            return _json({
                "type": "reservation_preview",
                "confirmation_token": token,
                "lab_id": lab_id,
                "equipment_id": equipment_id,
                "resource_name": lab.name if lab else None,
                "equipment_name": equipment.name if equipment else None,
                "date": data.date,
                "start_time": data.start_time,
                "end_time": data.end_time,
                "message": "预约预览已生成，必须等待用户点击确认后才能提交。",
            })
        except BusinessException as exc:
            return _json({"ok": False, "error": exc.message})
        except Exception:
            logger.exception("Reservation preview tool failed")
            return _json({"ok": False, "error": "预约预览暂时无法生成"})

    @tool
    def get_day() -> str:
        """获取实验室业务时区中的今天日期。"""
        return datetime.now(ZoneInfo(settings.BUSINESS_TIMEZONE)).date().isoformat()

    return [search_lab_docs, list_open_labs, list_lab_equipments,
            list_reservations, get_equipment_maintenance, get_operations_stats,
            create_lab_reservation, get_day]
