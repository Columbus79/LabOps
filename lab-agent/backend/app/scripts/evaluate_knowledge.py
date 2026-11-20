import argparse
import json
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.models.knowledge import KnowledgeChunk
from app.services.kb_service import evaluate_retrieval

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rag_eval.json"


def main():
    parser = argparse.ArgumentParser(description="Evaluate the indexed RAG corpus using the fixed local query set")
    parser.add_argument("--run", action="store_true", help="Query PostgreSQL and call the configured embedding API")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--fixture", type=Path, default=FIXTURE,
                        help="Fixed query/expected-source JSON; use a synthetic set for acceptance")
    args = parser.parse_args()
    cases = json.loads(args.fixture.read_text(encoding="utf-8"))
    if not args.run:
        print(json.dumps({"cases": len(cases), "categories": sorted({case["category"] for case in cases}),
                          "message": "Dry run; no database or model calls. Pass --run to evaluate."}, ensure_ascii=False))
        return
    db = SessionLocal()
    try:
        dimensions = sorted({row[0] for row in db.query(KnowledgeChunk.embedding_dimension).distinct().all()})
        result = evaluate_retrieval(db, cases, args.top_k)
        result.update({
            "embedding_model": settings.EMBEDDING_MODEL,
            "configured_dimensions": settings.EMBEDDING_DIMENSIONS,
            "indexed_dimensions": dimensions,
            "retrieval_mode": "exact cosine + full text + literal, reciprocal-rank fusion",
        })
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
