"""Data access for documents and their chunks (including vector search)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Chunk, Document


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: str
    document_title: str
    source_url: str | None
    content: str
    meta: dict
    similarity: float


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    # ---- documents ----
    def create(self, **fields) -> Document:
        doc = Document(**fields)
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get(self, document_id: uuid.UUID) -> Document | None:
        return self.db.get(Document, document_id)

    def get_by_filename(self, filename: str) -> Document | None:
        return self.db.scalar(select(Document).where(Document.filename == filename))

    def list_all(self) -> list[Document]:
        return list(self.db.scalars(select(Document).order_by(Document.created_at.desc())))

    def update(self, doc: Document, **fields) -> Document:
        for key, value in fields.items():
            setattr(doc, key, value)
        self.db.commit()
        return doc

    def delete(self, doc: Document) -> None:
        self.db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
        self.db.delete(doc)
        self.db.commit()

    # ---- chunks ----
    def add_chunks(self, document_id: uuid.UUID, items: list[tuple[str, dict, list[float]]]) -> int:
        self.db.add_all(
            Chunk(document_id=document_id, chunk_index=i, content=text, meta=meta, embedding=emb)
            for i, (text, meta, emb) in enumerate(items)
        )
        self.db.commit()
        return len(items)

    def search(self, query_embedding: list[float], top_k: int) -> list[RetrievedChunk]:
        """Cosine similarity search. pgvector's `<=>` returns cosine distance (1 - similarity)."""
        distance = Chunk.embedding.cosine_distance(query_embedding).label("distance")
        stmt = (
            select(Chunk, Document, distance)
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.status == "ready")
            .order_by(distance)
            .limit(top_k)
        )
        return [
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=str(doc.id),
                document_title=doc.title,
                source_url=doc.source_url,
                content=chunk.content,
                meta=chunk.meta or {},
                similarity=round(1.0 - float(dist), 4),
            )
            for chunk, doc, dist in self.db.execute(stmt)
        ]
