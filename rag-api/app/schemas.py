"""Pydantic models for API requests and responses."""

from datetime import datetime
from pydantic import BaseModel, Field


class IngestAccepted(BaseModel):
    job_id: str
    filenames: list[str]
    status: str = "processing"


class IngestStatus(BaseModel):
    job_id: str
    status: str  # processing | done | failed
    detail: str | None = None
    chunks_indexed: int = 0


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, description="The user question, in any language.")
    conversation_id: str | None = Field(default=None, description="Optional conversation ID to append message history.")


class Source(BaseModel):
    ref: int
    source: str
    text: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    question_type: str
    sub_questions: list[str]
    sources: list[Source]
    verified: bool
    trace_id: str | None = None
    conversation_id: str | None = None


# --- New schemas for Database features ---

class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    chunks_indexed: int
    error_detail: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True



class ConversationCreate(BaseModel):
    title: str = Field(min_length=1, description="The title of the conversation.")


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    status: str | None
    sources: list[Source] | None
    trace_id: str | None
    created_at: datetime

    class Config:
        from_attributes = True

