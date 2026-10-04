import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas import ChatRequest, ChatResponse
from app.services.chat_service import ChatService, ConversationNotFound

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def ask(
    body: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a question to the agent and get its answer (with sources)."""
    try:
        return ChatService(db).ask(user, body.question.strip(), body.conversation_id)
    except ConversationNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    except Exception as exc:  # LLM / embeddings / DB errors
        log.exception("Agent failed")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The agent could not answer right now (is the local model running?). Please try again.",
        ) from exc
