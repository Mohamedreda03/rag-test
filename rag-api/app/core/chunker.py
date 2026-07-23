"""Document parsing and parent-child chunking.

Small child chunks are indexed for precise search; their larger parent chunks
are returned to the generator for richer context.
"""

import io
import re
import uuid
from dataclasses import dataclass

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.config import Settings

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"[ \t]+")


@dataclass
class ChildChunk:
    """A small indexed chunk carrying its larger parent context."""

    id: str
    parent_id: str
    source: str
    text: str
    parent_text: str
    context: str = ""
    document_id: str = ""

    @property
    def index_text(self) -> str:
        """Text actually indexed: contextual summary + chunk body."""
        return f"{self.context}\n\n{self.text}".strip()


def extract_text(filename: str, data: bytes) -> str:
    """Extract plain text from PDF, DOCX, TXT, MD, or HTML files."""
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "pdf":
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if suffix == "docx":
        document = DocxDocument(io.BytesIO(data))
        return "\n\n".join(p.text for p in document.paragraphs if p.text.strip())
    if suffix in {"txt", "md", "markdown"}:
        return data.decode("utf-8", errors="ignore")
    if suffix in {"html", "htm"}:
        return _HTML_TAG_RE.sub(" ", data.decode("utf-8", errors="ignore"))
    raise ValueError(f"Unsupported file type: {filename!r}")


def build_chunks(text: str, source: str, settings: Settings, document_id: str = "") -> list[ChildChunk]:
    """Split a document into parent chunks, then each parent into child chunks."""
    # Normalize horizontal spaces without destroying line breaks and paragraphs
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(lines).strip()
    # Remove excessive blank lines (more than 2 consecutive newlines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    
    chunks: list[ChildChunk] = []
    for parent_text in _split_into_parents(cleaned, settings.parent_chunk_chars):
        parent_id = str(uuid.uuid4())
        for child_text in _split_with_overlap(
            parent_text, settings.child_chunk_chars, settings.child_chunk_overlap
        ):
            chunks.append(
                ChildChunk(
                    id=str(uuid.uuid4()),
                    parent_id=parent_id,
                    source=source,
                    text=child_text,
                    parent_text=parent_text,
                    document_id=document_id,
                )
            )
    return chunks


def _split_into_parents(text: str, max_chars: int) -> list[str]:
    """Group sections and paragraphs into parent chunks bounded by max_chars."""
    # Split text by headers or double newlines
    sections = re.split(r"(?=\n#{1,3}\s)|\n\n", text)
    sections = [s.strip() for s in sections if s and s.strip()]
    
    parents: list[str] = []
    buffer: list[str] = []
    size = 0
    
    for section in sections:
        sec_len = len(section)
        if size + sec_len + 2 > max_chars and buffer:
            parents.append("\n\n".join(buffer))
            buffer, size = [], 0
            
        if sec_len > max_chars:
            # Subdivide oversized section cleanly
            sub_pieces = _split_with_overlap(section, max_chars, overlap=100)
            parents.extend(sub_pieces)
            continue
            
        buffer.append(section)
        size += sec_len + 2
        
    if buffer:
        parents.append("\n\n".join(buffer))
    return parents


def _split_with_overlap(text: str, size: int, overlap: int) -> list[str]:
    """Sliding-window split that prefers breaking at newlines, periods, or whitespace."""
    if len(text) <= size:
        return [text]
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # Prefer breaking at newline or paragraph
            breakpoint_ = text.rfind("\n", start + size // 2, end)
            if breakpoint_ == -1:
                # Next choice: sentence end (. ! ?)
                match = re.search(r"[\.\!\?\n]\s", text[start + size // 2 : end])
                if match:
                    breakpoint_ = start + size // 2 + match.end()
            if breakpoint_ == -1:
                # Fallback to space
                breakpoint_ = text.rfind(" ", start + size // 2, end)
            if breakpoint_ != -1 and breakpoint_ > start:
                end = breakpoint_
                
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return pieces

