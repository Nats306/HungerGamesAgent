"""Orchestrates one chat turn: load/create the conversation, run the agent graph."""

import logging
import uuid

from sqlalchemy.orm import Session

from app.agent.graph import build_graph
from app.core.config import get_settings
from app.core.security import CurrentUser
from app.repositories import ConversationRepository, DocumentRepository
from app.services.embeddings import get_embeddings

log = logging.getLogger(__name__)


class ConversationNotFound(Exception):
    pass


class ChatService:
    def __init__(self, db: Session):
        self.db = db
        self.conversations = ConversationRepository(db)
        self.documents = DocumentRepository(db)

    def _search(self, query: str, top_k: int):
        return self.documents.search(get_embeddings().embed_query(query), top_k)

    def ask(self, user: CurrentUser, question: str, conversation_id: uuid.UUID | None) -> dict:
        settings = get_settings()
        if conversation_id is None:
            conversation = self.conversations.create(user.id, title=question[:80])
            history = []
        else:
            conversation = self.conversations.get_for_user(conversation_id, user.id)
            if conversation is None:
                raise ConversationNotFound()
            history = [
                {"role": m.role, "content": m.content}
                for m in self.conversations.recent_messages(conversation.id, settings.history_turns * 2)
            ]

        final_state = build_graph().invoke(
            {
                "question": question,
                "user_id": user.id,
                "conversation_id": str(conversation.id),
                "history": history,
            },
            config={
                "configurable": {"retriever": self._search, "history_store": self.conversations}
            },
        )
        log.info(
            "chat user=%s status=%s reason=%s",
            user.username, final_state["status"], final_state.get("reject_reason"),
        )
        return {
            "conversation_id": conversation.id,
            "answer": final_state["answer"],
            "status": final_state["status"],
            "sources": final_state.get("sources", []),
        }
