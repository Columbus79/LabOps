from types import SimpleNamespace

from app.services import kb_service


def test_retrieval_evaluation_reports_ranking_and_abstention(monkeypatch, db):
    found = {
        "known": [SimpleNamespace(source="distractor.md"), SimpleNamespace(source="rule.md")],
        "unknown": [],
    }
    monkeypatch.setattr(kb_service, "retrieve_chunks", lambda _db, query, _top_k: found[query])
    report = kb_service.evaluate_retrieval(db, [
        {"id": "one", "category": "semantic", "query": "known", "expected_sources": ["rule.md"]},
        {"id": "two", "category": "no_answer", "query": "unknown", "expected_sources": []},
    ], top_k=2)

    assert report["mean_recall_at_k"] == 1
    assert report["mean_precision_at_k"] == 0.5
    assert report["mean_reciprocal_rank"] == 0.5
    assert report["no_answer_abstention_accuracy"] == 1
    assert report["cases"][0]["first_relevant_rank"] == 2
    assert report["cases"][0]["latency_ms"] >= 0
