"""Document ingestion pipeline: extract -> split into chunks -> embed -> store in pgvector."""

import logging
import uuid
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories import DocumentRepository
from app.services.embeddings import get_embeddings
from app.services.extractors import Section, extract

log = logging.getLogger(__name__)


def split_sections(sections: list[Section]) -> list[tuple[str, dict]]:
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks: list[tuple[str, dict]] = []
    for section in sections:
        for piece in splitter.split_text(section.text):
            piece = piece.strip()
            if len(piece) >= 30:  # skip page numbers, lone headings, etc.
                chunks.append((piece, dict(section.meta)))
    return chunks


def process_document(document_id: uuid.UUID, filename: str, data: bytes) -> None:
    """Runs in the background after an upload. Uses its own DB session."""
    db = SessionLocal()
    repo = DocumentRepository(db)
    doc = repo.get(document_id)
    if doc is None:
        db.close()
        return
    try:
        sections = extract(filename, data)
        chunks = split_sections(sections)
        if not chunks:
            raise ValueError("No readable text was found in the file.")

        embeddings = get_embeddings().embed_documents([text for text, _ in chunks])
        count = repo.add_chunks(
            doc.id, [(text, meta, emb) for (text, meta), emb in zip(chunks, embeddings)]
        )
        repo.update(doc, status="ready", chunk_count=count, error=None)
        log.info("Document %s processed: %s chunks", filename, count)
    except Exception as exc:  # noqa: BLE001 - we want to store any failure reason
        log.exception("Failed to process %s", filename)
        db.rollback()
        repo.update(doc, status="failed", error=str(exc)[:1000])
    finally:
        db.close()


def title_from_filename(filename: str) -> str:
    return Path(filename).stem.replace("_", " ").replace("-", " ").strip() or filename
