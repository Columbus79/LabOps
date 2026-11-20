import asyncio
import json
import httpx
from langchain_openai.chat_models.base import OpenAIRateLimitError

from app.models.user import User
from app.models.audit import AgentToolExecution
from app.schemas.ai import ChatMessage, ChatRequest
from app.services import agent_service


def test_agent_stream_emits_safe_preview_and_tokens_once(monkeypatch, db, users_and_resources, caplog):
    student, _, _, _, _ = users_and_resources
    token = "opaque-confirmation-credential-that-is-long-enough-to-be-real"
    tool_output = json.dumps({
        "type": "reservation_preview", "confirmation_token": token,
        "lab_id": 7, "resource_name": "Research Lab", "equipment_id": None,
        "equipment_name": None, "date": "2099-12-01", "start_time": "10:00:00",
        "end_time": "11:00:00",
    })

    class FakeAgent:
        async def astream_events(self, input, version, config):
            yield {"event": "on_tool_end", "name": "create_lab_reservation", "data": {"output": tool_output}}
            yield {
                "event": "on_chat_model_stream",
                "metadata": {"langgraph_node": "agent"},
                "data": {"chunk": type("Chunk", (), {"content": "请核对预约信息。"})()},
            }

    monkeypatch.setattr(agent_service, "build_agent", lambda db, user: FakeAgent())
    request = ChatRequest(messages=[ChatMessage(role="user", content="预约实验室")])
    with caplog.at_level("INFO", logger="uvicorn.error"):
        events = asyncio.run(_collect(agent_service.stream_agent(
            db, student, request, trace_id="synthetic-trace-id")))

    preview = next(event for event in events if event["type"] == "reservation_preview")
    tool_end = next(event for event in events if event["type"] == "tool_end")
    assert preview["confirmation_token"] == token
    assert preview["resource_name"] == "Research Lab"
    assert token not in tool_end["preview"]
    assert [event["type"] for event in events][-2:] == ["token", "done"]
    assert "synthetic-trace-id" in caplog.text
    assert '"event": "agent_done"' in caplog.text
    assert token not in caplog.text


async def _collect(generator):
    return [event async for event in generator]


def test_booking_claim_without_tool_is_replaced(monkeypatch, db, users_and_resources):
    student, _, _, _, _ = users_and_resources

    class FakeAgent:
        async def astream_events(self, input, version, config):
            yield {"event": "on_chat_model_stream", "metadata": {"langgraph_node": "agent"},
                   "data": {"chunk": type("Chunk", (), {"content": "预约预览已生成，PREVIEW-FAKE。"})()}}

    monkeypatch.setattr(agent_service, "build_agent", lambda db, user: FakeAgent())
    request = ChatRequest(messages=[ChatMessage(role="user", content="请预约明天实验室")])
    events = asyncio.run(_collect(agent_service.stream_agent(db, student, request)))
    assert not any(event["type"] == "reservation_preview" for event in events)
    content = "".join(event["content"] for event in events if event["type"] == "token")
    assert "PREVIEW-FAKE" not in content
    assert "尚未生成" in content


def test_plain_text_knowledge_tool_result_is_audited(monkeypatch, db, users_and_resources):
    student, _, _, _, _ = users_and_resources

    class FakeAgent:
        async def astream_events(self, input, version, config):
            yield {"event": "on_tool_end", "name": "search_lab_docs",
                   "data": {"output": "[SYNTH_规则.md] 学生先提交预约。"}}
            yield {"event": "on_chat_model_stream", "metadata": {"langgraph_node": "agent"},
                   "data": {"chunk": type("Chunk", (), {"content": "请先提交预约。"})()}}

    monkeypatch.setattr(agent_service, "build_agent", lambda _db, _user: FakeAgent())
    request = ChatRequest(messages=[ChatMessage(role="user", content="查询知识库")])
    events = asyncio.run(_collect(agent_service.stream_agent(db, student, request)))

    assert events[-1]["type"] == "done"
    record = db.query(AgentToolExecution).one()
    assert record.tool_name == "search_lab_docs" and record.succeeded is True


def test_model_rate_limit_returns_specific_sse_error(monkeypatch, db, users_and_resources):
    student, _, _, _, _ = users_and_resources

    class RateLimitedAgent:
        async def astream_events(self, input, version, config):
            response = httpx.Response(429, request=httpx.Request("POST", "https://synthetic.invalid/v1/chat"))
            raise OpenAIRateLimitError("synthetic rate limit", response=response, body=None)
            yield  # pragma: no cover

    monkeypatch.setattr(agent_service, "build_agent", lambda _db, _user: RateLimitedAgent())
    request = ChatRequest(messages=[ChatMessage(role="user", content="查询实验室")])
    events = asyncio.run(_collect(agent_service.stream_agent(db, student, request)))

    assert events[-1] == {"type": "error", "message": "模型服务暂时限流，请稍后重试"}
