"""Operations metrics computed only from persisted PostgreSQL business records."""
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.maintenance import MaintenanceTicket
from app.models.reservation import Reservation


def operations(db: Session, start: date, end: date) -> dict:
    days = (end - start).days + 1
    if days < 1 or days > 90:
        raise BusinessException("统计日期范围必须为 1 至 90 天")
    labs = db.query(Lab).order_by(Lab.id).all()
    equipment = db.query(Equipment).order_by(Equipment.id).all()
    reservations = db.query(Reservation).filter(Reservation.date.between(start, end)).all()
    tickets = db.query(MaintenanceTicket).filter(
        func.date(MaintenanceTicket.create_time).between(start, end)
    ).all()

    completed_hours = {}
    for item in reservations:
        if item.status != 5 or not item.checked_in_at or not item.checked_out_at:
            continue
        reserved = (item.end_time.hour * 3600 + item.end_time.minute * 60 + item.end_time.second
                    - item.start_time.hour * 3600 - item.start_time.minute * 60 - item.start_time.second)
        actual = max(0, min((item.checked_out_at - item.checked_in_at).total_seconds(), reserved))
        key = ("equipment", item.equipment_id) if item.equipment_id else ("lab", item.lab_id)
        completed_hours[key] = completed_hours.get(key, 0.0) + actual / 3600

    def available_hours(lab):
        if not lab or not lab.open_time or not lab.close_time:
            return None
        opening = lab.open_time.hour * 60 + lab.open_time.minute
        closing = lab.close_time.hour * 60 + lab.close_time.minute
        return max(0, (closing - opening) / 60 * days)

    def resource_row(kind, item, lab):
        used = round(completed_hours.get((kind, item.id), 0.0), 3)
        available = available_hours(lab)
        return {"id": item.id, "name": item.name, "used_hours": used,
                "available_hours": round(available, 3) if available is not None else None,
                "utilization_rate": round(used / available * 100, 2) if available else None}

    lab_by_id = {item.id: item for item in labs}
    trend_counts = {start + timedelta(days=i): 0 for i in range(days)}
    for item in reservations:
        trend_counts[item.date] += 1
    reviewed = [item for item in reservations if item.review_result in (1, 2)]
    approved = sum(item.review_result == 1 for item in reviewed)
    repair_durations = [
        (item.handled_at - item.started_at).total_seconds() / 3600
        for item in tickets if item.started_at and item.handled_at and item.handled_at >= item.started_at
    ]
    frequency = {}
    for item in tickets:
        frequency[item.equipment_id] = frequency.get(item.equipment_id, 0) + 1
    return {
        "start": start.isoformat(), "end": end.isoformat(),
        "definition": "利用率=已签退的实际使用时长(最多计预约时长)/当前开放时段总时长；实验室预约与设备预约分别计算",
        "labs": [resource_row("lab", item, item) for item in labs],
        "equipments": [dict(resource_row("equipment", item, lab_by_id.get(item.lab_id)),
                            lab_id=item.lab_id) for item in equipment],
        "reservation_trend": [{"date": day.isoformat(), "count": count}
                              for day, count in trend_counts.items()],
        "reservation_total": len(reservations),
        "reviewed_total": len(reviewed),
        "approval_rate": round(approved / len(reviewed) * 100, 2) if reviewed else None,
        "no_show_total": sum(item.status == 6 for item in reservations),
        "repair_count": len(tickets),
        "average_repair_hours": round(sum(repair_durations) / len(repair_durations), 2)
        if repair_durations else None,
        "repair_frequency": [{"equipment_id": key, "count": value}
                             for key, value in sorted(frequency.items())],
    }
