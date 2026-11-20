from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app import config
from app.dependencies.auth import get_current_user
from app.main import app


def png_bytes():
    data = BytesIO()
    Image.new("RGB", (8, 8), "red").save(data, format="PNG")
    return data.getvalue()


def test_upload_requires_authentication(db, tmp_path):
    app.dependency_overrides.clear()
    config.UPLOAD_DIR = tmp_path
    with TestClient(app) as client:
        response = client.post("/api/files/upload", files={"file": ("safe.png", png_bytes(), "image/png")})
    assert response.status_code == 401
    assert list(tmp_path.iterdir()) == []


def test_upload_stream_checks_content_and_saves_server_name(db, users_and_resources, tmp_path):
    student, _, _, _, _ = users_and_resources
    config.UPLOAD_DIR = tmp_path
    app.dependency_overrides[get_current_user] = lambda: student
    try:
        with TestClient(app) as client:
            invalid = client.post("/api/files/upload", files={"file": ("spoof.png", b"not an image", "image/png")})
            assert invalid.status_code == 400
            assert list(tmp_path.iterdir()) == []

            valid = client.post("/api/files/upload", files={"file": ("../../portrait.png", png_bytes(), "image/png")})
            assert valid.status_code == 200
            result = valid.json()["data"]
            assert result["original_name"] == "portrait.png"
            assert result["disk_name"] != result["original_name"]
            assert (tmp_path / result["disk_name"]).is_file()
            assert client.get(result["url"]).content == png_bytes()
    finally:
        app.dependency_overrides.clear()


def test_office_attachment_requires_admin_and_is_not_public(db, users_and_resources, tmp_path):
    student, _, admin, _, _ = users_and_resources
    config.UPLOAD_DIR = tmp_path
    document = b"%PDF-1.4\nsynthetic test document\n%%EOF\n"
    app.dependency_overrides[get_current_user] = lambda: student
    try:
        with TestClient(app) as client:
            denied = client.post("/api/files/upload", files={"file": ("test.pdf", document, "application/pdf")})
            assert denied.status_code == 403
            assert list(tmp_path.iterdir()) == []

            app.dependency_overrides[get_current_user] = lambda: admin
            uploaded = client.post("/api/files/upload", files={"file": ("test.pdf", document, "application/pdf")})
            assert uploaded.status_code == 200
            path = uploaded.json()["data"]["url"]
            assert path.startswith("/api/files/download/")
            assert client.get(path).content == document
            assert client.get(path.replace("/api/files/download/", "/uploads/")).status_code == 404

            app.dependency_overrides[get_current_user] = lambda: student
            assert client.get(path).status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_legacy_resource_image_is_public_only_when_referenced(db, users_and_resources, tmp_path):
    _, _, _, lab, _ = users_and_resources
    config.UPLOAD_DIR = tmp_path
    filename = "1793958963101_fcac3766.png"
    unused = "1793958963102_abcdef12.png"
    (tmp_path / filename).write_bytes(png_bytes())
    (tmp_path / unused).write_bytes(png_bytes())
    lab.img = f"/uploads/{filename}"
    db.commit()
    with TestClient(app) as client:
        assert client.get(f"/uploads/{filename}").content == png_bytes()
        assert client.get(f"/uploads/{unused}").status_code == 404


def test_student_cannot_delete_equipment(db, users_and_resources):
    student, _, _, _, equipment = users_and_resources
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = lambda: student
    try:
        with TestClient(app) as client:
            response = client.delete(f"/api/equipment/{equipment.id}")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
