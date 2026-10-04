"""Bulk-load a folder of files into the knowledge base (as the 'system' user).

Files that were already loaded (same filename) are skipped, so it is safe to run it again.

Usage (inside the backend container):
    docker compose exec backend python -m scripts.seed /data
"""

import argparse
from pathlib import Path

from app.db.session import SessionLocal, init_db
from app.repositories import DocumentRepository
from app.services.document_service import DocumentService
from app.services.extractors import SUPPORTED_EXTENSIONS
from app.services.ingestion import process_document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default="/data")
    parser.add_argument("--force", action="store_true", help="Reload files that already exist")
    args = parser.parse_args()

    init_db()
    files = sorted(
        p for p in Path(args.folder).rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    print(f"Found {len(files)} files in {args.folder}")

    db = SessionLocal()
    repo, service = DocumentRepository(db), DocumentService(db)
    loaded = skipped = failed = 0
    for i, path in enumerate(files, start=1):
        existing = repo.get_by_filename(path.name)
        if existing and not args.force:
            skipped += 1
            continue
        if existing:
            repo.delete(existing)
        data = path.read_bytes()
        doc = service.register_upload(None, path.name, data)
        process_document(doc.id, doc.filename, data)
        db.refresh(doc)
        status = f"{doc.status} ({doc.chunk_count} chunks)" if doc.status == "ready" else f"FAILED: {doc.error}"
        print(f"[{i}/{len(files)}] {path.name}: {status}")
        loaded += doc.status == "ready"
        failed += doc.status != "ready"
    db.close()
    print(f"\nLoaded {loaded}, skipped {skipped} (already there), failed {failed}.")


if __name__ == "__main__":
    main()
