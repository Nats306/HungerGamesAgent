"""Text extraction for each supported file type.

Each extractor returns a list of `Section`s. A section is a piece of text plus metadata
(e.g. the page number of a PDF), so every chunk can later be traced back to its origin.
"""

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Section:
    text: str
    meta: dict = field(default_factory=dict)


class UnsupportedFileType(ValueError):
    pass


SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown", ".csv", ".docx"}


def _pdf(data: bytes) -> list[Section]:
    import fitz  # PyMuPDF

    sections = []
    with fitz.open(stream=data, filetype="pdf") as pdf:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()
            if text:
                sections.append(Section(text, {"page": page_number}))
    return sections


def _plain(data: bytes) -> list[Section]:
    text = data.decode("utf-8", errors="replace")
    return [Section(text)] if text.strip() else []


def _markdown(data: bytes) -> list[Section]:
    """Split markdown by headings so each chunk keeps the heading it belongs to."""
    text = data.decode("utf-8", errors="replace")
    # Drop a YAML front-matter block if present (used by the wiki scraper for metadata).
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :]

    sections: list[Section] = []
    heading, buffer = None, []

    def flush():
        body = "\n".join(buffer).strip()
        if body:
            prefix = f"{heading}\n" if heading else ""
            sections.append(Section(prefix + body, {"section": heading} if heading else {}))

    for line in text.splitlines():
        if line.startswith("#"):
            flush()
            heading, buffer = line.lstrip("#").strip(), []
        else:
            buffer.append(line)
    flush()
    return sections


def _csv(data: bytes) -> list[Section]:
    """Each row becomes a 'column: value' line so the LLM can read it."""
    reader = csv.DictReader(io.StringIO(data.decode("utf-8", errors="replace")))
    sections = []
    for row_number, row in enumerate(reader, start=1):
        line = "; ".join(f"{k}: {v}" for k, v in row.items() if k and v)
        if line:
            sections.append(Section(line, {"row": row_number}))
    return sections


def _docx(data: bytes) -> list[Section]:
    import docx

    document = docx.Document(io.BytesIO(data))
    text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
    return [Section(text)] if text else []


_EXTRACTORS = {
    ".pdf": _pdf,
    ".txt": _plain,
    ".md": _markdown,
    ".markdown": _markdown,
    ".csv": _csv,
    ".docx": _docx,
}


def extract(filename: str, data: bytes) -> list[Section]:
    ext = Path(filename).suffix.lower()
    extractor = _EXTRACTORS.get(ext)
    if extractor is None:
        raise UnsupportedFileType(
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    return extractor(data)


def parse_front_matter(data: bytes) -> dict:
    """Read `key: value` pairs from a markdown front-matter block (title, source_url...)."""
    text = data.decode("utf-8", errors="replace")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    meta = {}
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"')
    return meta
