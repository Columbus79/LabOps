import json
import logging
import re
from time import perf_counter
from typing import Any

from langchain_openai import ChatOpenAI
from openai import RateLimitError
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from sqlalchemy.orm import Session
from app.config import settings
from app.common.exceptions import BusinessException
from app.models.user import User
from app.models.audit import AgentToolExecution
from app.observability import trace_event
from app.schemas.ai import ChatRequest
from app.services import agent_tools
from app.services import conversation_service
logger = logging.getLogger("labops.agent")

SYSTEM_PROMPT = """你是 LabOps 实验室运营助手。仅依据工具返回的真实业务数据回答，保持简洁。
可用工具：实验室、设备、我的预约、维修状态、知识库、运营统计和预约预览。
用户提到今天、明天、后天时先调用 get_day。缺少资源 ID 时先查询资源，不猜测。
用户请求预约且信息齐全时，必须实际调用 create_lab_reservation。只有工具成功返回
type=reservation_preview 时，才能说“预览已生成”。不得编造预览 ID、确认凭证、工具结果或数据库记录。
工具失败或未调用时，明确说明未生成预览，并询问缺少的信息。
预约预览只供核对；真实写入必须由用户在页面点击确认按钮，后端验证凭证。
预约审核通过后才能签到使用。规则和安全问题优先检索知识库。
没有权限的统计或其他用户数据不要透露。对无关问题简短说明服务范围。
"""
TOOL_LABELS = {
    "search_lab_docs": "检索实验室知识库",
    "list_open_labs": "查询开放的实验室",
    "list_lab_equipments": "查询实验室设备",
    "create_lab_reservation": "创建预约单",
    "get_day": "获取今天的日期",
    "list_reservations": "查询预约记录",
    "get_equipment_maintenance": "查询设备维修状态",
    "get_operations_stats": "查询运营统计",
}


def _build_history(data: ChatRequest):
    """前端消息转成langchain需要的消息对象"""
    history = []
    for message in data.messages:
        if message.role == "user" and message.content.strip():
            history.append(HumanMessage(content=message.content.strip()))
        elif message.role == "assistant" and message.content.strip():
            history.append(AIMessage(content=message.content.strip()))
    if not history:
        raise BusinessException(message="请输入您的对话内容")
    return history


def _tool_output_preview(output: Any, limit: int = 200):
    """把工具输出的结果收成短preview 避免整段 JSON 刷到前端过程区"""
    if isinstance(output, ToolMessage):
        output = output.content
    text = output if isinstance(output, str) else str(output)
    try:
        payload = json.loads(text)
        if payload.get("type") == "reservation_preview":
            return "预约预览已生成，等待用户明确确认"
    except (ValueError, TypeError):
        pass
    return text if len(text) <= limit else text[:limit] + "..."


def _chunk_text(chunk: Any):
    """
    从模型的流式输出里面 拿到纯文本
    chunk.content 可能是str [{type, text, ......}]等类型 需要统一处理成字符串

    """
    if chunk is None:
        return ""
    # chunk 如果是AIMessage则可以去除content
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(part.get("text") or "")
        return "".join(parts)
    return str(content) if content is not None else ""


async def stream_agent(db: Session, current_user: User, data: ChatRequest,
                       conversation_id: int | None = None, trace_id: str | None = None):
    """
    生成器：边运行 Agent 边 yield 事件，提供 SSE 输出给前端
    事件类型：status | tool_start | tool_end | token | done | error
    """
    started = perf_counter()
    tool_started = {}
    tool_count = 0
    input_tokens = None
    output_tokens = None
    try:
        history = _build_history(data)
        agent = build_agent(db, current_user)

        inputs = {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                *history,
            ]
        }

        yield {"type": "status", "message": "正在思考"}
        if conversation_id is not None:
            yield {"type": "conversation", "conversation_id": conversation_id}
        assistant_parts = []
        booking_request = bool(re.search(r"预约|预览|订用", history[-1].content))
        actual_preview = False
        tool_inputs = {}

        async for event in agent.astream_events(
            input=inputs,
            version="v2",
            config={"recursion_limit": 10},
        ):
            kind = event.get("event")

            # 工具开始执行
            if kind == "on_tool_start":
                name = event.get("name") or ""
                if name not in TOOL_LABELS:
                    continue
                run_id = str(event.get("run_id", ""))
                tool_inputs[run_id] = (event.get("data") or {}).get("input")
                tool_started[run_id] = perf_counter()

                yield {
                    "type": "tool_start",
                    "name": name,
                    "label": TOOL_LABELS.get(name, name),
                }

            # 工具执行结束
            elif kind == "on_tool_end":
                name = event.get("name") or ""
                if name not in TOOL_LABELS:
                    continue

                output = (event.get("data") or {}).get("output")
                yield {
                    "type": "tool_end",
                    "name": name,
                    "label": TOOL_LABELS.get(name, name),
                    "preview": _tool_output_preview(output),
                }
                preview = _reservation_preview(output)
                if preview:
                    actual_preview = True
                    yield preview
                succeeded = True
                try:
                    value = output.content if isinstance(output, ToolMessage) else output
                    try:
                        parsed = json.loads(value) if isinstance(value, str) else value
                    except (ValueError, TypeError):
                        parsed = {}
                    succeeded = not (isinstance(parsed, dict) and parsed.get("ok") is False)
                    db.add(AgentToolExecution(
                        conversation_id=conversation_id, user_id=current_user.id,
                        tool_name=name[:80],
                        input_summary=json.dumps(tool_inputs.pop(str(event.get("run_id", "")), None),
                                                 ensure_ascii=False, default=str)[:2000],
                        output_summary=_tool_output_preview(output, 300), succeeded=succeeded,
                    ))
                    db.commit()
                except Exception:
                    db.rollback()
                    logger.exception("Could not persist Agent tool execution")
                tool_count += 1
                run_id = str(event.get("run_id", ""))
                tool_start = tool_started.pop(run_id, None)
                trace_event("agent_tool", trace_id=trace_id, conversation_id=conversation_id,
                            tool=name, succeeded=succeeded,
                            duration_ms=round((perf_counter() - tool_start) * 1000, 2)
                            if tool_start is not None else None)

            elif kind == "on_tool_error":
                name = event.get("name") or ""
                if name not in TOOL_LABELS:
                    continue
                yield {"type": "tool_end", "name": name,
                       "label": TOOL_LABELS[name], "preview": "工具执行失败"}
                try:
                    db.add(AgentToolExecution(
                        conversation_id=conversation_id, user_id=current_user.id,
                        tool_name=name[:80],
                        input_summary=json.dumps(tool_inputs.pop(str(event.get("run_id", "")), None),
                                                 ensure_ascii=False, default=str)[:2000],
                        output_summary="工具执行失败", succeeded=False,
                    ))
                    db.commit()
                except Exception:
                    db.rollback()
                    logger.exception("Could not persist failed Agent tool execution")
                tool_count += 1
                run_id = str(event.get("run_id", ""))
                tool_start = tool_started.pop(run_id, None)
                trace_event("agent_tool", trace_id=trace_id, conversation_id=conversation_id,
                            tool=name, succeeded=False,
                            duration_ms=round((perf_counter() - tool_start) * 1000, 2)
                            if tool_start is not None else None)

            elif kind == "on_chat_model_end":
                message = (event.get("data") or {}).get("output")
                usage = getattr(message, "usage_metadata", None) or {}
                if usage.get("input_tokens") is not None:
                    input_tokens = (input_tokens or 0) + usage["input_tokens"]
                if usage.get("output_tokens") is not None:
                    output_tokens = (output_tokens or 0) + usage["output_tokens"]

            # 大模型流式输出
            if kind == "on_chat_model_stream":

                metadata = event.get("metadata") or {}

                if metadata.get("langgraph_node") not in (None, "agent"):
                    continue

                chunk = (event.get("data") or {}).get("chunk")

                text = _chunk_text(chunk)
                if text:
                    assistant_parts.append(text)
                    if not booking_request:
                        yield {"type": "token", "content": text}

        response_text = "".join(assistant_parts)
        if booking_request:
            if not actual_preview and re.search(r"预览.{0,8}已生成|已生成.{0,8}预览|确认凭证|预览\s*ID|PREVIEW-", response_text, re.I):
                response_text = "尚未生成可确认的预约预览。请提供实验室、设备（如需）、日期和时段后重试。"
            if response_text:
                yield {"type": "token", "content": response_text}

        if conversation_id is not None and response_text:
            conversation_service.append_assistant_message(
                db, current_user, conversation_id, response_text
            )
        trace_event("agent_done", trace_id=trace_id, conversation_id=conversation_id,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    tool_calls=tool_count, preview_generated=actual_preview,
                    input_tokens=input_tokens, output_tokens=output_tokens)
        yield {"type": "done"}

    except BusinessException as e:
        trace_event("agent_error", trace_id=trace_id, conversation_id=conversation_id,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    error_type="business")
        yield {
            "type": "error",
            "message": e.message,
        }

    except RateLimitError:
        logger.warning("Agent model provider rate limited the request")
        trace_event("agent_error", trace_id=trace_id, conversation_id=conversation_id,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    error_type="rate_limit")
        yield {"type": "error", "message": "模型服务暂时限流，请稍后重试"}

    except Exception:
        logger.exception("Agent stream failed")
        trace_event("agent_error", trace_id=trace_id, conversation_id=conversation_id,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    error_type="internal")

        yield {
            "type": "error",
            "message": "大模型调用失败 请稍后重试",
        }


def build_agent(db: Session, current_user: User):
    api_key = settings.LLM_API_KEY.get_secret_value().strip() if settings.LLM_API_KEY else ""
    if not api_key or not settings.LLM_MODEL or not settings.LLM_BASE_URL:
        raise BusinessException("AI 助手尚未配置模型服务")
    tools = agent_tools.build_tools(db, current_user)

    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=api_key,
        base_url=settings.LLM_BASE_URL,
        temperature=0,
        timeout=settings.AGENT_REQUEST_TIMEOUT_SECONDS,
        max_retries=1,
        streaming=True,  # Stream this result  stream_event 接收到逐字返回的token
    ).bind_tools(tools)

    async def agent_node(state: MessagesState):
        """langGraph 执行工作流的节点"""
        response = await llm.ainvoke(state["messages"])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)  # 调用大模型的节点
    graph.add_node(
        "tools", ToolNode(tools=tools)
    )  # 根据tool call中的参数信息决定具体执行tools中tool的节点
    graph.add_edge(START, "agent")  # 流程的起点 call LLM
    graph.add_conditional_edges(
        "agent", tools_condition
    )  # 看有无tool call 有就继续 没有就end
    graph.add_edge("tools", "agent")  # 让agent看tool调用的结果
    return graph.compile()


def _reservation_preview(output: Any):
    if isinstance(output, ToolMessage):
        output = output.content
    if not isinstance(output, str):
        return None
    try:
        payload = json.loads(output)
    except (ValueError, TypeError):
        return None
    if payload.get("type") != "reservation_preview":
        return None
    return {
        "type": "reservation_preview",
        "confirmation_token": payload["confirmation_token"],
        "lab_id": payload["lab_id"],
        "resource_name": payload.get("resource_name"),
        "equipment_id": payload.get("equipment_id"),
        "equipment_name": payload.get("equipment_name"),
        "date": payload["date"],
        "start_time": payload["start_time"],
        "end_time": payload["end_time"],
    }

