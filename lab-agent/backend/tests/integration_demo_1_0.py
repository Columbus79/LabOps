"""Explicit HTTP integration check against the backed-up, isolated DEMO database.

Run only before archiving the DEMO database. Credentials are read from a local
0600 file; this script never prints passwords or JWTs.
"""
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    accounts = json.loads(args.credentials.read_text(encoding="utf-8"))
    root = args.base_url.rstrip("/") + "/api"

    def call(method, path, token=None, expected=200, **kwargs):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = requests.request(method, root + path, headers=headers, timeout=20, **kwargs)
        assert response.status_code == expected, (path, response.status_code, response.text[:300])
        return response.json()

    def login(name):
        result = call("POST", "/auth/login", json=accounts[name])
        return result["data"]["token"]

    admin = login("demo_admin")
    student = login("demo_student_a")
    other = login("demo_student_b")
    existing = call("GET", "/lab/list", admin, params={"page_size": 100})["data"]["list"]
    assert any(item["name"] == "DEMO-Lab-A" for item in existing), "Refusing non-DEMO database"

    lab = call("POST", "/lab", admin, json={
        "name": "DEMO-1.0-Operations", "location": "DEMO-Acceptance",
        "capacity": 8, "open_time": "00:00", "close_time": "23:59",
        "description": "Synthetic product acceptance fixture", "status": 1,
    })["data"]
    lab_id = lab["id"]
    call("PUT", f"/lab/{lab_id}", admin, json={"location": "DEMO-Acceptance-Updated"})
    equipment = call("POST", "/equipment", admin, json={
        "lab_id": lab_id, "name": "DEMO-1.0-Device", "quantity": 2, "status": 1,
    })["data"]
    equipment_id = equipment["id"]
    call("PUT", f"/equipment/{equipment_id}", admin, json={"quantity": 3})

    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    assert now.hour < 22, "Run live check-in verification before 22:00 Asia/Shanghai"
    start = now.replace(second=0, microsecond=0)
    end = start + timedelta(minutes=45)
    slot = {"lab_id": lab_id, "equipment_id": equipment_id,
            "date": now.date().isoformat(), "start_time": start.time().isoformat(timespec="minutes"),
            "end_time": end.time().isoformat(timespec="minutes"),
            "remark": "DEMO-1.0-lifecycle"}
    call("POST", "/reservation", student, json=slot)
    page = call("GET", "/reservation/list", student, params={"page_size": 100})["data"]["list"]
    booking = next(item for item in page if item["remark"] == slot["remark"])
    booking_id = booking["id"]
    call("PUT", f"/reservation/{booking_id}/audit", admin, json={"status": 1})
    call("PUT", f"/reservation/{booking_id}/check-in", other, expected=403)
    active = call("PUT", f"/reservation/{booking_id}/check-in", student)["data"]
    assert active["status"] == 4 and active["checked_in_at"]
    completed = call("PUT", f"/reservation/{booking_id}/check-out", student)["data"]
    assert completed["status"] == 5 and completed["checked_out_at"]

    future = {**slot, "date": (now.date() + timedelta(days=1)).isoformat(),
              "start_time": "11:00", "end_time": "12:00", "remark": "DEMO-1.0-fault"}
    call("POST", "/reservation", student, json=future)
    page = call("GET", "/reservation/list", student, params={"page_size": 100})["data"]["list"]
    affected_id = next(item["id"] for item in page if item["remark"] == future["remark"])
    call("PUT", f"/reservation/{affected_id}/audit", admin, json={"status": 1})
    ticket = call("POST", "/maintenance", student, json={
        "equipment_id": equipment_id, "description": "DEMO synthetic product fault",
    })["data"]
    page = call("GET", "/reservation/list", student, params={"page_size": 100})["data"]["list"]
    assert next(item["status"] for item in page if item["id"] == affected_id) == 7
    call("PUT", f"/maintenance/{ticket['id']}", admin,
         json={"status": "repairing", "repair_notes": "DEMO diagnosis"})
    repaired = call("PUT", f"/maintenance/{ticket['id']}", admin,
                    json={"status": "completed", "repair_notes": "DEMO repair complete"})["data"]
    assert repaired["started_at"] and repaired["handled_at"]
    devices = call("GET", "/equipment/list", student, params={"lab_id": lab_id})["data"]["list"]
    assert next(item["status"] for item in devices if item["id"] == equipment_id) == 1

    report = call("GET", "/dashboard/operations", admin,
                  params={"start": now.date().isoformat(),
                          "end": (now.date() + timedelta(days=1)).isoformat()})["data"]
    assert report["reservation_total"] >= 2 and report["approval_rate"] == 100
    assert report["repair_count"] >= 1 and report["average_repair_hours"] is not None
    assert any(item["id"] == lab_id for item in report["labs"])
    assert any(item["id"] == equipment_id for item in report["equipments"])
    assert call("GET", "/audit", admin)["data"]["total"] >= 8
    call("GET", "/audit", other, expected=403)
    assert call("GET", "/notifications", student)["data"]["total"] >= 1
    print({"result": "passed", "database": "backed-up DEMO PostgreSQL",
           "lab_id": lab_id, "equipment_id": equipment_id,
           "completed_reservation": booking_id, "fault_interrupted_reservation": affected_id,
           "maintenance_ticket": ticket["id"], "approval_rate": report["approval_rate"]})


if __name__ == "__main__":
    main()
