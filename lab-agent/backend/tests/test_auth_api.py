from fastapi.testclient import TestClient

from app.main import app
from app.dependencies.auth import get_current_user


def test_register_login_and_password_validation(db):
    with TestClient(app) as client:
        invalid = client.post("/api/auth/register", json={
            "username": "short", "password": "tiny", "name": "Student",
        })
        assert invalid.status_code == 422

        registered = client.post("/api/auth/register", json={
            "username": "new-student", "password": "long-enough-password", "name": "Student",
        })
        assert registered.status_code == 200

        logged_in = client.post("/api/auth/login", json={
            "username": "new-student", "password": "long-enough-password",
        })
        assert logged_in.status_code == 200
        assert len(logged_in.headers["X-Request-ID"]) == 32
        payload = logged_in.json()["data"]
        assert payload["user"]["role"] == "student"
        assert payload["token"]
        assert "password" not in payload["user"]

        wrong_password = client.post("/api/auth/login", json={
            "username": "new-student", "password": "wrong-password",
        })
        assert wrong_password.status_code == 400


def test_student_cannot_access_admin_user_api(db, users_and_resources):
    student, _, _, _, _ = users_and_resources
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = lambda: student
    try:
        with TestClient(app) as client:
            response = client.get("/api/user/list")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
