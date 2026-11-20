from types import SimpleNamespace

from app.services.kb_service import reciprocal_rank_fusion, split_markdown


def test_markdown_split_keeps_chunks_bounded_and_overlapping():
    text = ("第一段内容。" * 90) + "\n\n" + ("第二段内容。" * 90)
    chunks = split_markdown(text, chunk_size=300, overlap=40)
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 300 for chunk in chunks)


def test_rrf_combines_vector_and_keyword_results():
    vector = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    keyword = [SimpleNamespace(id=2), SimpleNamespace(id=3)]
    assert [item.id for item in reciprocal_rank_fusion(vector, keyword)] == [2, 1, 3]
