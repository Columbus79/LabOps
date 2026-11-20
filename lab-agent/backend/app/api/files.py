import os
import re
import uuid
import zipfile
from pathlib import Path
from PIL import Image, UnidentifiedImageError

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse as DownloadResponse

from app import config
from app.common.exceptions import BusinessException
from app.common.response import Response
from app.dependencies.auth import get_current_admin, get_current_user
from app.schemas.file import FileResponse

router = APIRouter(prefix="/files", tags=["文件管理"])
CHUNK_SIZE = 64 * 1024
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MIME_BY_EXT = {
    ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"},
    ".png": {"image/png"}, ".gif": {"image/gif"},
    ".webp": {"image/webp"}, ".pdf": {"application/pdf"},
    ".doc": {"application/msword", "application/octet-stream"},
    ".xls": {"application/vnd.ms-excel", "application/octet-stream"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip", "application/octet-stream"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip", "application/octet-stream"},
    ".zip": {"application/zip", "application/x-zip-compressed", "application/octet-stream"},
}


def _matches_signature(ext: str, header: bytes, path: Path) -> bool:
    if ext in {".jpg", ".jpeg"}:
        valid_header = header.startswith(b"\xff\xd8\xff")
        return valid_header and _image_decodes(path)
    if ext == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n") and _image_decodes(path)
    if ext == ".gif":
        return header.startswith((b"GIF87a", b"GIF89a")) and _image_decodes(path)
    if ext == ".webp":
        return header.startswith(b"RIFF") and header[8:12] == b"WEBP" and _image_decodes(path)
    if ext == ".pdf":
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 1024))
            trailer = stream.read()
        return header.startswith(b"%PDF-") and b"%%EOF" in trailer
    if ext in {".doc", ".xls"}:
        return header.startswith(bytes.fromhex("D0CF11E0A1B11AE1"))
    if ext in {".zip", ".docx", ".xlsx"}:
        if not zipfile.is_zipfile(path):
            return False
        try:
            with zipfile.ZipFile(path) as archive:
                members = archive.infolist()
                if len(members) > 200 or sum(item.file_size for item in members) > 50 * 1024 * 1024:
                    return False
                names = {item.filename for item in members}
                if archive.testzip() is not None:
                    return False
                if ext == ".docx":
                    return "word/document.xml" in names
                if ext == ".xlsx":
                    return "xl/workbook.xml" in names
                return True
        except (OSError, zipfile.BadZipFile, RuntimeError):
            return False
    return False


def _image_decodes(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError):
        return False


@router.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    if not file.filename:
        raise BusinessException(message="文件名不能为空")
    original_name = Path(file.filename.replace("\\", "/")).name
    ext = Path(original_name).suffix.lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise BusinessException(message="不支持的文件类型")
    if ext not in IMAGE_EXTENSIONS and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可以上传办公附件")
    declared_type = (file.content_type or "application/octet-stream").split(";", 1)[0].lower()
    if declared_type not in MIME_BY_EXT[ext]:
        raise BusinessException(message="文件 MIME 类型与扩展名不匹配")

    upload_root = config.UPLOAD_DIR.resolve()
    disk_name = f"{uuid.uuid4().hex}{ext}"
    save_path = upload_root / disk_name
    size = 0
    header = b""
    try:
        fd = os.open(save_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        with os.fdopen(fd, "wb") as target:
            while chunk := file.file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > config.MAX_FILE_SIZE:
                    raise BusinessException(message="文件超过最大限制")
                if len(header) < 512:
                    header += chunk[: 512 - len(header)]
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        if size == 0 or not _matches_signature(ext, header, save_path):
            raise BusinessException(message="文件内容与扩展名不匹配或文件为空")
    except Exception:
        save_path.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()

    return Response.success(
        data=FileResponse(
            original_name=original_name,
            disk_name=disk_name,
            size=size,
            url=(f"/uploads/{disk_name}" if ext in IMAGE_EXTENSIONS
                 else f"/api/files/download/{disk_name}"),
        )
    )


@router.get("/download/{disk_name}")
def download_document(disk_name: str, _admin=Depends(get_current_admin)):
    """Office attachments are never served by the public /uploads route."""
    if not re.fullmatch(r"[0-9a-f]{32}\.(?:pdf|doc|docx|xls|xlsx|zip)", disk_name):
        raise HTTPException(status_code=404, detail="File not found")
    path = config.UPLOAD_DIR / disk_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return DownloadResponse(path, filename=disk_name, media_type="application/octet-stream")
