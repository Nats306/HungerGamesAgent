import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas import DocumentOut
from app.services.document_service import (
    DocumentNotFound,
    DocumentService,
    FileTooLarge,
    NotAllowed,
)
from app.services.extractors import UnsupportedFileType
from app.services.ingestion import process_document

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _out(service: DocumentService, user: CurrentUser, doc) -> DocumentOut:
    out = DocumentOut.model_validate(doc)
    out.can_delete = service.can_delete(user, doc)
    return out


@router.post("", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a file. It is processed in the background: poll GET /api/documents/{id}
    until `status` is `ready` (or `failed`)."""
    data = await file.read()
    service = DocumentService(db)
    try:
        doc = service.register_upload(user, file.filename or "upload", data)
    except FileTooLarge as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc))
    except (UnsupportedFileType, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    background.add_task(process_document, doc.id, doc.filename, data)
    return _out(service, user, doc)


@router.get("", response_model=list[DocumentOut])
def list_documents(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    service = DocumentService(db)
    return [_out(service, user, d) for d in service.list_all()]


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = DocumentService(db)
    try:
        return _out(service, user, service.get(document_id))
    except DocumentNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a document and its embeddings. Only its uploader or an admin can do it."""
    try:
        DocumentService(db).delete(user, document_id)
    except DocumentNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    except NotAllowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only delete your own documents")
