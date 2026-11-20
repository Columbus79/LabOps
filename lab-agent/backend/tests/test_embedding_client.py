from pydantic import SecretStr

import pytest

from app.config import settings
from app.utils import embedding


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"data": [
            {"index": 1, "embedding": [3, 4]},
            {"index": 0, "embedding": [1, 2]},
        ]}


def test_embedding_client_checks_and_orders_dimensions(monkeypatch):
    monkeypatch.setattr(settings, "SILICONFLOW_EMBEDDING_API_KEY", SecretStr("test-key"))
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSIONS", 2)
    calls = []
    monkeypatch.setattr(embedding.requests, "post", lambda *args, **kwargs: (calls.append((args, kwargs)) or FakeResponse()))
    vectors = embedding.get_embeddings(["first", "second"])
    assert vectors == [[1.0, 2.0], [3.0, 4.0]]
    assert calls[0][1]["timeout"] == (5, 45)
    assert calls[0][1]["json"]["input"] == ["first", "second"]


def test_embedding_client_rejects_dimension_mismatch(monkeypatch):
    class WrongDimension(FakeResponse):
        def json(self):
            return {"data": [{"index": 0, "embedding": [1, 2, 3]}]}

    monkeypatch.setattr(settings, "SILICONFLOW_EMBEDDING_API_KEY", SecretStr("test-key"))
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSIONS", 2)
    monkeypatch.setattr(embedding.requests, "post", lambda *args, **kwargs: WrongDimension())
    with pytest.raises(ValueError, match="dimension"):
        embedding.get_embedding("test")
