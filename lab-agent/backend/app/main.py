import logging
import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import api
from app.common.exceptions import (
    BusinessException,
    business_exception_hadler,
    global_exception_hadler,
    http_exception_hadler,
    validation_exception_hadler,
)
from app import config
from app.config import settings
from app.database import engine, get_db
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.user import User
from app.observability import request_trace

logger = logging.getLogger("labops")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema changes are applied only through Alembic; API workers never mutate schema
    # or start duplicate reservation-expiration loops.
    if engine.dialect.name != "postgresql" and settings.APP_ENV.lower() != "testing":
        raise RuntimeError(
            "LabOps runtime requires the migrated PostgreSQL database; "
            "the original MySQL source is read-only until migration is approved."
        )
    yield
    engine.dispose()


app = FastAPI(title="LabOps API", version="1.0.0", lifespan=lifespan)
app.middleware("http")(request_trace)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Last-Event-ID"],
    expose_headers=["X-Request-ID"],
)
app.include_router(api)
app.add_exception_handler(BusinessException, business_exception_hadler)
app.add_exception_handler(HTTPException, http_exception_hadler)
app.add_exception_handler(RequestValidationError, validation_exception_hadler)
app.add_exception_handler(Exception, global_exception_hadler)

@app.get("/uploads/{disk_name}", tags=["files"])
def public_image(disk_name: str, db: Session = Depends(get_db)):
    """Only uploaded image assets are public; office files use the authenticated API."""
    new_name = re.fullmatch(r"[0-9a-f]{32}\.(?:jpg|jpeg|png|gif|webp)", disk_name)
    legacy_name = re.fullmatch(r"[0-9]{13}_[0-9a-f]{8}\.(?:jpg|jpeg|png|gif|webp)", disk_name)
    if not new_name and not legacy_name:
        raise HTTPException(status_code=404, detail="File not found")
    if legacy_name:
        reference = f"/uploads/{disk_name}"
        referenced = (db.query(Lab.id).filter(Lab.img == reference).first()
                      or db.query(Equipment.id).filter(Equipment.img == reference).first()
                      or db.query(User.id).filter(User.avatar == reference).first())
        if not referenced:
            raise HTTPException(status_code=404, detail="File not found")
    path = config.UPLOAD_DIR / disk_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)


@app.get("/health/live", tags=["health"])
def liveness():
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def readiness():
    try:
        if engine.dialect.name != "postgresql" and settings.APP_ENV.lower() != "testing":
            raise RuntimeError("PostgreSQL target database is required")
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Database readiness check failed")
        from fastapi import HTTPException as FastAPIHTTPException

        raise FastAPIHTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ready"}


@app.get("/")
def root():
    return {"message": "LabOps API is running"}
