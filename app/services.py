from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm import LLMClient, ModelMessage
from app.models import Conversation, Message
from app.prompts import CRISIS_KEYWORDS, CRISIS_REPLY, SYSTEM_PROMPT
from app.schemas import ChatRequest


class ConversationNotFound(LookupError):
    pass


@dataclass(frozen=True)
class ChatResult:
    conversation_id: int
    reply: str
    provider: str
    safety_triggered: bool


def contains_crisis_signal(text: str) -> bool:
    normalized = text.replace(" ", "").lower()
    return any(keyword in normalized for keyword in CRISIS_KEYWORDS)


class ChatService:
    """Coordinate conversation state, safety, model calls and persistence."""

    def __init__(self, llm: LLMClient, history_limit: int = 20) -> None:
        self.llm = llm
        self.history_limit = history_limit

    def chat(self, db: Session, request: ChatRequest) -> ChatResult:
        conversation = self._get_or_create_conversation(
            db, request.conversation_id, request.message
        )

        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=request.message,
        )
        db.add(user_message)
        db.commit()

        if contains_crisis_signal(request.message):
            return self._store_reply(
                db,
                conversation,
                CRISIS_REPLY,
                provider="safety",
                safety_triggered=True,
            )

        history = self._recent_history(db, conversation.id)
        model_messages = [ModelMessage(role="system", content=SYSTEM_PROMPT)]
        model_messages.extend(
            ModelMessage(role=item.role, content=item.content) for item in history
        )

        reply = self.llm.complete(model_messages)
        return self._store_reply(
            db,
            conversation,
            reply,
            provider=self.llm.provider,
            safety_triggered=False,
        )

    def get_history(self, db: Session, conversation_id: int) -> Conversation:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            raise ConversationNotFound

        conversation.messages = list(
            db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at, Message.id)
            ).all()
        )
        return conversation

    def delete_conversation(self, db: Session, conversation_id: int) -> None:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            raise ConversationNotFound
        db.delete(conversation)
        db.commit()

    def _get_or_create_conversation(
        self,
        db: Session,
        conversation_id: int | None,
        first_message: str,
    ) -> Conversation:
        if conversation_id is not None:
            conversation = db.get(Conversation, conversation_id)
            if conversation is None:
                raise ConversationNotFound
            return conversation

        title = first_message[:30] or "新的对话"
        conversation = Conversation(title=title)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    def _recent_history(self, db: Session, conversation_id: int) -> list[Message]:
        newest_first = list(
            db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(self.history_limit)
            ).all()
        )
        return list(reversed(newest_first))

    def _store_reply(
        self,
        db: Session,
        conversation: Conversation,
        reply: str,
        provider: str,
        safety_triggered: bool,
    ) -> ChatResult:
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=reply,
        )
        conversation.updated_at = datetime.now(timezone.utc)
        db.add(assistant_message)
        db.commit()
        return ChatResult(
            conversation_id=conversation.id,
            reply=reply,
            provider=provider,
            safety_triggered=safety_triggered,
        )
