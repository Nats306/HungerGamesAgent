"""Request / response models of the API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SourceOut(BaseModel):
    index: int
    document_id: str
    title: str
    source_url: str | None = None
    page: int | None = None
    section: str | None = None
    similarity: float
    snippet: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    answer: str
    # answered | rejected | greeting | clarification
    status: str
    sources: list[SourceOut] = []


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    status: str | None = None
    sources: list[SourceOut] = []
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    title: str
    source_url: str | None = None
    content_type: str
    status: str
    error: str | None = None
    chunk_count: int
    uploaded_by_name: str
    created_at: datetime
    can_delete: bool = False


class UserOut(BaseModel):
    id: str
    username: str
    email: str | None = None
    roles: list[str]
