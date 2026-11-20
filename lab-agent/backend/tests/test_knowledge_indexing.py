from app.models.knowledge import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument, KnowledgeDocumentVersion
from app.services import kb_service


def test_index_persists_success_and_skips_unchanged_documents(db, tmp_path):
    (tmp_path / "safety.md").write_text("\n  \n", encoding="utf-8")

    first = kb_service.index_markdown_documents(db, tmp_path)
    second = kb_service.index_markdown_documents(db, tmp_path)

    assert first["documents"] == [{"document_id": "safety", "status": "failed", "chunks": 0,
                                   "error": "BusinessException"}]
    assert second["documents"] == [{"document_id": "safety", "status": "failed", "chunks": 0,
                                    "error": "BusinessException"}]
    document = db.query(KnowledgeDocument).filter_by(document_id="safety").one()
    assert document.status == "failed"
    assert document.last_error == "BusinessException"
    assert len(document.content_hash) == 64


def test_index_records_embedding_failure_without_exposing_exception_text(db, tmp_path, monkeypatch):
    (tmp_path / "safety.md").write_text("预约前确认设备状态。", encoding="utf-8")

    def fail(_texts):
        raise RuntimeError("provider response included sensitive details")

    monkeypatch.setattr(kb_service, "get_embeddings", fail)
    result = kb_service.index_markdown_documents(db, tmp_path)

    assert result["documents"] == [{
        "document_id": "safety", "status": "failed", "chunks": 0, "error": "RuntimeError",
    }]
    document = db.query(KnowledgeDocument).filter_by(document_id="safety").one()
    assert document.status == "failed"
    assert document.last_error == "RuntimeError"


def test_index_updates_changed_chunks_and_failure_keeps_previous_index(db, tmp_path, monkeypatch):
    source = tmp_path / "safety.md"
    source.write_text("first indexed content", encoding="utf-8")
    monkeypatch.setattr(kb_service.settings, "EMBEDDING_DIMENSIONS", 2)
    monkeypatch.setattr(kb_service, "get_embeddings", lambda texts: [[1.0, 0.0] for _ in texts])

    first = kb_service.index_markdown_documents(db, tmp_path)
    first_hash = db.query(KnowledgeChunk.content_hash).one()[0]
    source.write_text("updated indexed content", encoding="utf-8")
    updated = kb_service.index_markdown_documents(db, tmp_path)
    second_hash = db.query(KnowledgeChunk.content_hash).one()[0]

    assert first["documents"][0]["status"] == "indexed"
    assert updated["documents"][0]["status"] == "indexed"
    assert first_hash != second_hash
    assert db.query(KnowledgeChunk.content).one()[0] == "updated indexed content"
    assert db.query(KnowledgeDocument.version).one()[0] == 2
    assert [row.version for row in db.query(KnowledgeDocumentVersion).order_by(KnowledgeDocumentVersion.version)] == [1, 2]

    source.write_text("third version cannot be embedded", encoding="utf-8")
    def embedding_failure(_texts):
        raise RuntimeError("private")

    monkeypatch.setattr(kb_service, "get_embeddings", embedding_failure)
    failed = kb_service.index_markdown_documents(db, tmp_path)

    assert failed["documents"][0]["status"] == "failed"
    assert failed["documents"][0]["chunks"] == 1
    assert db.query(KnowledgeChunk.content).one()[0] == "updated indexed content"
    assert db.query(KnowledgeDocument.status).one()[0] == "failed"
    assert db.query(KnowledgeDocument.version).one()[0] == 2


def test_missing_source_does_not_silently_delete_indexed_document(db, tmp_path, monkeypatch):
    source = tmp_path / "rules.md"
    source.write_text("Synthetic booking rule", encoding="utf-8")
    monkeypatch.setattr(kb_service.settings, "EMBEDDING_DIMENSIONS", 2)
    monkeypatch.setattr(kb_service, "get_embeddings", lambda texts: [[1.0, 0.0] for _ in texts])
    kb_service.index_markdown_documents(db, tmp_path)
    source.unlink()
    result = kb_service.index_markdown_documents(db, tmp_path)
    assert result["removed_documents"] == []
    assert db.query(KnowledgeDocument).filter_by(document_id="rules").count() == 1
