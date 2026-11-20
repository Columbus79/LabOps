import hashlib
import io
import logging
import re
from pathlib import Path
from time import perf_counter

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.config import BASE_DIR, settings
from app.database import utc_now
from app.models.knowledge import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument, KnowledgeDocumentVersion
from app.utils.embedding import get_embeddings, get_embedding

logger = logging.getLogger("labops.knowledge")
KB_DIR = BASE_DIR / "data" / "kb"
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 120
RRF_CONSTANT = 60
SUPPORTED_DOCUMENTS = {".md", ".txt", ".pdf", ".docx", ".xlsx", ".pptx"}
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024


def split_markdown(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"\r\n?", "\n", text).strip()
    if not text:
        return []
    if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap must be smaller than chunk_size")
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        if end < len(text):
            # Prefer a Markdown paragraph boundary when it is near the chunk end.
            boundary = text.rfind("\n\n", start + chunk_size // 2, end)
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def extract_document_text(path: Path) -> str:
    """Read local office files; callers decide explicitly whether to embed them."""
    raw = path.read_bytes()
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise BusinessException("知识文档超过 5 MB 限制")
    suffix = path.suffix.lower()
    if suffix in (".md", ".txt"):
        text = raw.decode("utf-8-sig")
    elif suffix == ".pdf":
        from pypdf import PdfReader
        text = "\n\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
    elif suffix == ".docx":
        from docx import Document
        document = Document(io.BytesIO(raw))
        lines = [p.text for p in document.paragraphs]
        lines.extend(cell.text for table in document.tables for row in table.rows for cell in row.cells)
        text = "\n".join(lines)
    elif suffix == ".xlsx":
        from openpyxl import load_workbook
        workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        lines = []
        for sheet in workbook.worksheets:
            lines.append(sheet.title)
            for row in sheet.iter_rows(values_only=True):
                lines.append(" | ".join(str(value) for value in row if value is not None))
        workbook.close()
        text = "\n".join(lines)
    elif suffix == ".pptx":
        from pptx import Presentation
        presentation = Presentation(io.BytesIO(raw))
        text = "\n".join(shape.text for slide in presentation.slides
                         for shape in slide.shapes if shape.has_text_frame)
    else:
        raise BusinessException("不支持的知识文档类型")
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        raise BusinessException("知识文档没有可提取文本")
    return text


def _document_chunks(path: Path):
    text = extract_document_text(path)
    chunks = split_markdown(text)
    document_id = path.stem if path.suffix.lower() == ".md" else path.name
    return document_id, path.name, chunks


def index_markdown_documents(db: Session, directory: Path = KB_DIR):
    """Incrementally index explicitly selected local files; never prune other sources."""
    processed = []
    paths = sorted(path for path in directory.iterdir()
                   if path.is_file() and path.suffix.lower() in SUPPORTED_DOCUMENTS)
    for path in paths:
        document_id = path.stem if path.suffix.lower() == ".md" else path.name
        source = path.name
        try:
            text = extract_document_text(path)
            chunks = split_markdown(text)
            document_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            rows = [
                (chunk_index, content,
                 hashlib.sha256((document_id + "\0" + content).encode("utf-8")).hexdigest())
                for chunk_index, content in enumerate(chunks)
            ]
            document = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.document_id == document_id
            ).one_or_none()
            old = db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document_id).all()
            if (document and document.status == "indexed" and document.content_hash == document_hash
                    and [row.content_hash for row in old] == [row[2] for row in rows]):
                processed.append({"document_id": document_id, "status": "unchanged", "chunks": len(rows)})
                continue

            # Fetch and validate every embedding before replacing any existing chunks.
            embeddings = get_embeddings([row[1] for row in rows]) if rows else []
            if len(embeddings) != len(rows):
                raise BusinessException("Embedding 服务返回的向量数量不一致")
            if settings.EMBEDDING_DIMENSIONS and any(
                len(vector) != settings.EMBEDDING_DIMENSIONS for vector in embeddings
            ):
                raise BusinessException("Embedding 向量维度与配置不一致")
            dimensions = {len(vector) for vector in embeddings}
            if len(dimensions) > 1:
                raise BusinessException("Embedding 服务返回的向量维度不一致")

            now = utc_now()
            if document is None:
                document = KnowledgeDocument(document_id=document_id, title=path.stem,
                                             source=source, content_hash=document_hash,
                                             chunk_count=len(rows), status="indexed", indexed_at=now,
                                             version=1)
                db.add(document)
                # Sessions disable autoflush; persist the parent before inserting FK-linked chunks.
                db.flush()
            else:
                document.version += 1
                document.title = path.stem
                document.source = source
                document.content_hash = document_hash
                document.chunk_count = len(rows)
                document.status = "indexed"
                document.last_error = None
                document.indexed_at = now
            db.add(KnowledgeDocumentVersion(document_id=document_id, version=document.version,
                                            source=source, content_hash=document_hash,
                                            indexed_at=now))
            db.query(KnowledgeChunk).filter(
                KnowledgeChunk.document_id == document_id
            ).delete(synchronize_session="fetch")
            for row, embedding in zip(rows, embeddings):
                db.add(KnowledgeChunk(
                    document_id=document_id,
                    title=path.stem,
                    source=source,
                    chunk_index=row[0],
                    content_hash=row[2],
                    content=row[1],
                    embedding_dimension=len(embedding),
                    embedding=embedding,
                ))
            db.commit()
            processed.append({"document_id": document_id, "status": "indexed", "chunks": len(rows)})
        except Exception as exc:
            # Roll back replacement work first, then persist a sanitized failure state.
            db.rollback()
            document = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.document_id == document_id
            ).one_or_none()
            if document is None:
                document = KnowledgeDocument(document_id=document_id, title=path.stem, source=source,
                                             content_hash="0" * 64, chunk_count=0,
                                             status="failed", last_error=type(exc).__name__)
                db.add(document)
            else:
                document.status = "failed"
                document.last_error = type(exc).__name__
            db.commit()
            retained_chunks = document.chunk_count
            logger.error("Failed to index knowledge document %s (%s)", document_id, type(exc).__name__)
            processed.append({"document_id": document_id, "status": "failed",
                              "chunks": retained_chunks, "error": type(exc).__name__})

    return {"documents": processed, "removed_documents": []}


def reciprocal_rank_fusion(vector_rows, keyword_rows, k: int = RRF_CONSTANT):
    scores = {}
    rows_by_id = {}
    for rows in (vector_rows, keyword_rows):
        for rank, row in enumerate(rows, start=1):
            key = row.id
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            rows_by_id[key] = row
    return sorted(rows_by_id.values(), key=lambda row: scores[row.id], reverse=True)


def retrieve_chunks(db: Session, query: str, top_k: int = 5):
    query = query.strip()
    if not query:
        return []
    if db.query(KnowledgeChunk.id).first() is None:
        return []
    top_k = min(max(top_k, 1), 10)
    vector_rows = []
    try:
        embedding = get_embedding(query)
        dimensions = db.query(KnowledgeChunk.embedding_dimension).distinct().all()
        known_dimensions = {row[0] for row in dimensions}
        if known_dimensions and known_dimensions != {len(embedding)}:
            raise BusinessException("查询向量维度与已索引文档不一致")
        distance = KnowledgeChunk.embedding.cosine_distance(embedding)
        # This query orders every matching vector by exact cosine distance; no ANN index is claimed.
        vector_results = db.query(KnowledgeChunk, distance.label("distance")).order_by(distance).limit(top_k * 4).all()
        vector_rows = [row for row, dist in vector_results if 1.0 - float(dist) >= settings.RAG_MIN_SIMILARITY]
    except BusinessException:
        raise
    except Exception:
        db.rollback()
        logger.warning("Vector retrieval unavailable; returning keyword matches", exc_info=True)

    tsquery = func.plainto_tsquery("simple", query)
    tsvector = func.to_tsvector("simple", KnowledgeChunk.content)
    rank = func.ts_rank_cd(tsvector, tsquery)
    try:
        full_text_rows = db.query(KnowledgeChunk).filter(tsvector.op("@@")(tsquery)).order_by(rank.desc()).limit(top_k * 4).all()
        literal_rows = db.query(KnowledgeChunk).filter(KnowledgeChunk.content.ilike(f"%{query}%")).limit(top_k * 4).all()
        keyword_rows = reciprocal_rank_fusion(full_text_rows, literal_rows)
    except Exception:
        db.rollback()
        # A PostgreSQL-specific query should not make a mocked or transitional DB unusable.
        keyword_rows = db.query(KnowledgeChunk).filter(KnowledgeChunk.content.ilike(f"%{query}%")).limit(top_k * 4).all()
    return reciprocal_rank_fusion(vector_rows, keyword_rows)[:top_k]


def search(db: Session, query: str, top_k: int = 5):
    ranked = retrieve_chunks(db, query, top_k)
    return "\n\n".join(
        f"[{row.source} · {row.title} · 分块 {row.chunk_index + 1}]\n{row.content}"
        for row in ranked
    )


def evaluate_retrieval(db: Session, cases: list[dict], top_k: int = 5):
    results = []
    recall_values = []
    precision_values = []
    reciprocal_ranks = []
    abstention_cases = []
    for case in cases:
        started = perf_counter()
        rows = retrieve_chunks(db, case["query"], top_k)
        ranked_sources = [row.source for row in rows]
        expected = set(case.get("expected_sources", []))
        found = expected.intersection(ranked_sources)
        recall = len(found) / len(expected) if expected else None
        precision = sum(source in expected for source in ranked_sources[:top_k]) / top_k if top_k > 0 else 0.0
        first_relevant_rank = next((rank for rank, source in enumerate(ranked_sources, 1)
                                    if source in expected), None)
        reciprocal_rank = 1.0 / first_relevant_rank if first_relevant_rank else 0.0
        if expected:
            recall_values.append(recall)
            precision_values.append(precision)
            reciprocal_ranks.append(reciprocal_rank)
        else:
            abstention_cases.append(not ranked_sources)
        results.append({
            "id": case["id"],
            "category": case["category"],
            "expected_sources": sorted(expected),
            "ranked_sources": ranked_sources,
            "recall_at_k": recall,
            "precision_at_k": precision if expected else None,
            "reciprocal_rank": reciprocal_rank if expected else None,
            "first_relevant_rank": first_relevant_rank,
            "abstained": not ranked_sources,
            "latency_ms": round((perf_counter() - started) * 1000, 2),
        })
    return {
        "top_k": top_k,
        "answerable_cases": len(recall_values),
        "no_answer_cases": len(abstention_cases),
        "mean_recall_at_k": sum(recall_values) / len(recall_values) if recall_values else 0.0,
        "mean_precision_at_k": sum(precision_values) / len(precision_values) if precision_values else 0.0,
        "mean_reciprocal_rank": sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0,
        "no_answer_abstention_accuracy": sum(abstention_cases) / len(abstention_cases) if abstention_cases else None,
        "mean_latency_ms": round(sum(case["latency_ms"] for case in results) / len(results), 2) if results else None,
        "cases": results,
    }
