import json
from datetime import datetime, timezone
import uuid
from typing import Any

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class DBFolderDocument(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, nullable=True)
    filename = Column(String, nullable=False)
    status = Column(String, nullable=False)  # 'processing', 'done', 'failed'
    chunks_indexed = Column(Integer, default=0)
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class DBConversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    messages = relationship("DBMessage", back_populates="conversation", cascade="all, delete-orphan", lazy="selectin")


class DBMessage(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # 'user', 'assistant'
    content = Column(Text, nullable=False)
    status = Column(String, nullable=True)
    sources = Column(Text, nullable=True)  # JSON array string
    trace_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    conversation = relationship("DBConversation", back_populates="messages")


class DatabaseHelper:
    def __init__(self, database_url: str) -> None:
        self.engine = create_async_engine(database_url)
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def init_tables(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
