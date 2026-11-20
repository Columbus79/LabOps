from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin, get_current_user
from app.models.knowledge_document import KnowledgeDocument, KnowledgeDocumentVersion
from app.services.kb_service import retrieve_chunks

router = APIRouter(prefix="/knowledge", tags=["知识库"])


@router.get("/search")
def search(query: str = Query(min_length=1, max_length=500), top_k: int = Query(5, ge=1, le=10),
           _user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = retrieve_chunks(db, query, top_k)
    versions = {doc.document_id: doc.version for doc in db.query(KnowledgeDocument).filter(
        KnowledgeDocument.document_id.in_([row.document_id for row in rows])
    ).all()} if rows else {}
    return Response.success(data=[{
        "document_id": row.document_id, "source": row.source,
        "title": row.title, "version": versions.get(row.document_id),
        "chunk_index": row.chunk_index, "content": row.content,
    } for row in rows])


@router.get("/documents")
def list_documents(_admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    items = db.query(KnowledgeDocument).order_by(KnowledgeDocument.document_id).all()
    return Response.success(data=[{
        "document_id": item.document_id, "title": item.title, "source": item.source,
        "version": item.version, "status": item.status, "chunk_count": item.chunk_count,
        "indexed_at": item.indexed_at,
    } for item in items])


@router.get("/documents/{document_id}/versions")
def list_versions(document_id: str, _admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    items = db.query(KnowledgeDocumentVersion).filter(
        KnowledgeDocumentVersion.document_id == document_id
    ).order_by(KnowledgeDocumentVersion.version.desc()).all()
    return Response.success(data=[{
        "version": item.version, "source": item.source,
        "content_hash": item.content_hash, "indexed_at": item.indexed_at,
    } for item in items])
