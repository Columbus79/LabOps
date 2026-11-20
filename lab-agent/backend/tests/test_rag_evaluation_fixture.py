import json
from pathlib import Path


def test_fixed_rag_dataset_covers_required_query_classes():
    fixture = Path(__file__).resolve().parents[1] / "app" / "fixtures" / "rag_eval.json"
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    categories = {case["category"] for case in cases}
    assert categories == {"semantic", "keyword", "multi_document", "no_answer", "low_relevance", "document_update"}
    assert all(case.get("expected_sources") is not None for case in cases)
