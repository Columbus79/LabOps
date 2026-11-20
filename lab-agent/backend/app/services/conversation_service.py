from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.database import utc_now
from app.models.agent import AgentConversation, AgentMessage
from app.models.user import User
from app.schemas.ai import ChatMessage

CONTEXT_MESSAGE_LIMIT = 20


def _owned_conversation(db: Session, user: User, conversation_id: int):
    conversation = db.query(AgentConversation).filter(
        AgentConversation.id == conversation_id,
        AgentConversation.user_id == user.id,
    ).first()
    if not conversation:
        raise BusinessException("对话不存在", code=404)
    return conversation


def create_conversation(db: Session, user: User, title: str = "新对话"):
    conversation = AgentConversation(user_id=user.id, title=title[:120])
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(db: Session, user: User):
    return db.query(AgentConversation).filter(
        AgentConversation.user_id == user.id
    ).order_by(AgentConversation.update_time.desc()).limit(100).all()


def get_messages(db: Session, user: User, conversation_id: int):
    _owned_conversation(db, user, conversation_id)
    return db.query(AgentMessage).filter(
        AgentMessage.conversation_id == conversation_id
    ).order_by(AgentMessage.id.asc()).limit(200).all()


def append_user_turn(db: Session, user: User, data):
    user_message = next((m.content.strip() for m in reversed(data.messages) if m.role == "user" and m.content.strip()), None)
    if not user_message:
        raise BusinessException("请输入您的对话内容")

    if data.conversation_id is None:
        conversation = create_conversation(db, user, user_message[:80])
    else:
        conversation = _owned_conversation(db, user, data.conversation_id)
    db.add(AgentMessage(conversation_id=conversation.id, role="user", content=user_message))
    conversation.update_time = utc_now()
    db.commit()

    messages = db.query(AgentMessage).filter(
        AgentMessage.conversation_id == conversation.id
    ).order_by(AgentMessage.id.desc()).limit(CONTEXT_MESSAGE_LIMIT).all()
    messages.reverse()
    prompt = [ChatMessage(role=m.role, content=m.content) for m in messages]
    return conversation.id, prompt


def append_assistant_message(db: Session, user: User, conversation_id: int, content: str):
    if not content.strip():
        return
    conversation = _owned_conversation(db, user, conversation_id)
    db.add(AgentMessage(conversation_id=conversation_id, role="assistant", content=content[:8000]))
    conversation.update_time = utc_now()
    db.commit()
