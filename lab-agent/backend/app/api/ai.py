import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.audit import AgentToolExecution
from app.schemas.ai import ChatRequest
from app.schemas.reservation import ReservationConfirmationRequest
from sqlalchemy.orm import Session

from app.services import agent_service
from app.services import conversation_service
from app.services.confirmation_service import confirm_reservation

router = APIRouter(prefix="/ai", tags=["AI相关的API"])


@router.post("/chat/stream")
async def chat(
    data: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation_id, prompt_messages = conversation_service.append_user_turn(
        db, current_user, data
    )
    prompt_data = ChatRequest(messages=prompt_messages, conversation_id=conversation_id)

    async def event_gen():
        async for event in agent_service.stream_agent(
            db, current_user, prompt_data, conversation_id, trace_id=request.state.trace_id
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",  # 告诉浏览器这是 SSE 流
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 避免整段吐出去
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/conversations")
def create_conversation(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = conversation_service.create_conversation(db, current_user)
    return Response.success(data={"id": item.id, "title": item.title})


@router.get("/conversations")
def list_conversations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = conversation_service.list_conversations(db, current_user)
    return Response.success(data=[
        {"id": item.id, "title": item.title, "update_time": item.update_time}
        for item in items
    ])


@router.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(conversation_id: int, current_user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    items = conversation_service.get_messages(db, current_user, conversation_id)
    return Response.success(data=[
        {"id": item.id, "role": item.role, "content": item.content, "create_time": item.create_time}
        for item in items
    ])


@router.get("/conversations/{conversation_id}/tools")
def get_conversation_tools(conversation_id: int, current_user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    conversation_service.get_messages(db, current_user, conversation_id)
    items = db.query(AgentToolExecution).filter(
        AgentToolExecution.conversation_id == conversation_id,
        AgentToolExecution.user_id == current_user.id,
    ).order_by(AgentToolExecution.id).all()
    return Response.success(data=[{
        "id": item.id, "tool_name": item.tool_name, "succeeded": item.succeeded,
        "input_summary": item.input_summary, "output_summary": item.output_summary,
        "create_time": item.create_time,
    } for item in items])


@router.post("/reservations/confirm")
def confirm_agent_reservation(
    data: ReservationConfirmationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation = confirm_reservation(db, current_user, data.token)
    return Response.success(message="预约已提交，等待管理员审核", data={"reservation_id": reservation.id})
