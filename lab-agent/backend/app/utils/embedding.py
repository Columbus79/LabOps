import logging

import requests

from app.config import settings

logger = logging.getLogger("labops.embedding")
EMBEDDING_URL = "https://api.siliconflow.cn/v1/embeddings"


def get_embeddings(texts: list[str]) -> list[list[float]]:
    api_key = (
        settings.SILICONFLOW_EMBEDDING_API_KEY.get_secret_value().strip()
        if settings.SILICONFLOW_EMBEDDING_API_KEY else ""
    )
    if not api_key:
        raise RuntimeError("SiliconFlow Embedding API key is not configured")
    if not texts:
        return []
    response = requests.post(
        EMBEDDING_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"input": texts, "model": settings.EMBEDDING_MODEL},
        timeout=(5, 45),
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != len(texts):
        raise ValueError("Embedding provider returned an unexpected number of vectors")
    vectors = []
    for item in sorted(data, key=lambda row: row.get("index", 0)):
        vector = item.get("embedding")
        if not isinstance(vector, list) or not vector:
            raise ValueError("Embedding provider returned an empty vector")
        if not all(isinstance(value, (int, float)) for value in vector):
            raise ValueError("Embedding provider returned non-numeric vector values")
        if settings.EMBEDDING_DIMENSIONS and len(vector) != settings.EMBEDDING_DIMENSIONS:
            raise ValueError("Embedding dimension differs from EMBEDDING_DIMENSIONS")
        vectors.append([float(value) for value in vector])
    dimensions = {len(vector) for vector in vectors}
    if len(dimensions) != 1:
        raise ValueError("Embedding provider returned inconsistent vector dimensions")
    return vectors


def get_embedding(text: str) -> list[float]:
    return get_embeddings([text])[0]
