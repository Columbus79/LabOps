import pytest

from app.common.exceptions import BusinessException
from app.models.notification import Notification
from app.schemas.ai import ChatMessage, ChatRequest
from app.services import conversation_service, notification_service


def test_conversations_are_persisted_and_private(db, users_and_resources):
    student, other, _, _, _ = users_and_resources
    request = ChatRequest(messages=[ChatMessage(role="user", content="预约规则是什么？")])
    conversation_id, prompt = conversation_service.append_user_turn(db, student, request)
    assert [message.content for message in prompt] == ["预约规则是什么？"]
    conversation_service.append_assistant_message(db, student, conversation_id, "请先提交预约并等待审核。")
    assert len(conversation_service.get_messages(db, student, conversation_id)) == 2
    with pytest.raises(BusinessException, match="不存在"):
        conversation_service.get_messages(db, other, conversation_id)


def test_notifications_are_scoped_to_the_authenticated_user(db, users_and_resources):
    student, other, _, _, _ = users_and_resources
    db.add_all([
        Notification(user_id=student.id, event_type="test", title="Mine", message="Own notification"),
        Notification(user_id=other.id, event_type="test", title="Other", message="Private notification"),
    ])
    db.commit()
    listed = notification_service.list_notifications(db, student)
    assert listed["total"] == 1
    assert listed["list"][0].title == "Mine"
    notification_service.mark_read(db, student, listed["list"][0].id)
    assert notification_service.unread_count(db, student) == 0
    assert notification_service.unread_count(db, other) == 1
