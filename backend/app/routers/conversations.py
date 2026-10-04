import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db
from app.repositories import ConversationRepository
from app.schemas import ConversationDetail, ConversationOut

router = APIRouter(prefix="/api/conversations", tags=["history"])


@router.get("", response_model=list[ConversationOut])
def list_conversations(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Conversation history of the logged-in user (newest first)."""
    return ConversationRepository(db).list_for_user(user.id)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = ConversationRepository(db)
    conv = repo.get_for_user(conversation_id, user.id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=repo.messages(conv.id),
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = ConversationRepository(db)
    conv = repo.get_for_user(conversation_id, user.id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    repo.delete(conv)
