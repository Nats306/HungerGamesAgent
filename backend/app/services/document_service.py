"""Business rules for the knowledge-base documents."""

import mimetypes
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import CurrentUser
from app.models import Document
from app.repositories import DocumentRepository
from app.services.extractors import SUPPORTED_EXTENSIONS, UnsupportedFileType, parse_front_matter
from app.services.ingestion import title_from_filename


class DocumentNotFound(Exception):
    pass


class NotAllowed(Exception):
    pass


class FileTooLarge(ValueError):
    pass


class DocumentService:
    def __init__(self, db: Session):
        self.repo = DocumentRepository(db)
        self.settings = get_settings()

    def can_delete(self, user: CurrentUser, doc: Document) -> bool:
        return doc.uploaded_by == user.id or user.has_role(self.settings.admin_role)

    def register_upload(self, user: CurrentUser | None, filename: str, data: bytes) -> Document:
        """Validate the file and create the DB row (status=processing).
        The heavy work (embeddings) runs afterwards in `ingestion.process_document`."""
        filename = Path(filename).name  # avoid path tricks
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFileType(
                f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )
        if len(data) > self.settings.max_upload_mb * 1024 * 1024:
            raise FileTooLarge(f"File is larger than {self.settings.max_upload_mb} MB")
        if not data:
            raise ValueError("The file is empty")

        front = parse_front_matter(data) if ext in {".md", ".markdown"} else {}
        return self.repo.create(
            filename=filename,
            title=front.get("title") or title_from_filename(filename),
            source_url=front.get("source_url"),
            content_type=mimetypes.guess_type(filename)[0] or "application/octet-stream",
            status="processing",
            uploaded_by=user.id if user else "system",
            uploaded_by_name=user.username if user else "system",
        )

    def list_all(self) -> list[Document]:
        return self.repo.list_all()

    def get(self, document_id: uuid.UUID) -> Document:
        doc = self.repo.get(document_id)
        if doc is None:
            raise DocumentNotFound()
        return doc

    def delete(self, user: CurrentUser, document_id: uuid.UUID) -> None:
        doc = self.get(document_id)
        if not self.can_delete(user, doc):
            raise NotAllowed()
        self.repo.delete(doc)
