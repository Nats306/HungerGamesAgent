"""Data access for conversations and messages (chat history)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Conversation, Message


class ConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: str, title: str) -> Conversation:
        conv = Conversation(user_id=user_id, title=title[:255])
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def get_for_user(self, conversation_id: uuid.UUID, user_id: str) -> Conversation | None:
        return self.db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )

    def list_for_user(self, user_id: str) -> list[Conversation]:
        return list(
            self.db.scalars(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.updated_at.desc())
            )
        )

    def messages(self, conversation_id: uuid.UUID) -> list[Message]:
        return list(
            self.db.scalars(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
            )
        )

    def recent_messages(self, conversation_id: uuid.UUID, limit: int) -> list[Message]:
        rows = list(
            self.db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.id.desc())
                .limit(limit)
            )
        )
        return list(reversed(rows))

    def add_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        status: str | None = None,
        sources: list | None = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            status=status,
            sources=sources or [],
        )
        self.db.add(msg)
        conv = self.db.get(Conversation, conversation_id)
        if conv is not None:
            conv.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def delete(self, conv: Conversation) -> None:
        self.db.delete(conv)
        self.db.commit()
