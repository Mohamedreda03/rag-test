import json
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from app.db import DBConversation, DBMessage
from app.schemas import ConversationResponse, MessageResponse, ConversationCreate, Source

router = APIRouter()


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(request: Request) -> list[ConversationResponse]:
    if not request.app.state.db:
        return []
    async with request.app.state.db.session_factory() as session:
        result = await session.execute(
            select(DBConversation).order_by(DBConversation.created_at.desc())
        )
        conversations = result.scalars().all()
        return conversations


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: Request, body: ConversationCreate) -> ConversationResponse:
    if not request.app.state.db:
        import uuid
        from datetime import datetime, timezone
        return ConversationResponse(
            id=str(uuid.uuid4()),
            title=body.title,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    async with request.app.state.db.session_factory() as session:
        conversation = DBConversation(title=body.title)
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation


@router.get("/conversations/{id}/messages", response_model=list[MessageResponse])
async def list_conversation_messages(request: Request, id: str) -> list[MessageResponse]:
    if not request.app.state.db:
        return []
    async with request.app.state.db.session_factory() as session:
        # Check if conversation exists
        conv_result = await session.execute(
            select(DBConversation).where(DBConversation.id == id)
        )
        if not conv_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Conversation not found")

        result = await session.execute(
            select(DBMessage).where(DBMessage.conversation_id == id).order_by(DBMessage.created_at.asc())
        )
        messages = result.scalars().all()
        
        parsed_messages = []
        for msg in messages:
            sources_list = None
            if msg.sources:
                try:
                    sources_list = json.loads(msg.sources)
                except Exception:
                    sources_list = []
            
            parsed_messages.append(
                MessageResponse(
                    id=msg.id,
                    conversation_id=msg.conversation_id,
                    role=msg.role,
                    content=msg.content,
                    status=msg.status,
                    sources=sources_list,
                    trace_id=msg.trace_id,
                    created_at=msg.created_at,
                )
            )
        return parsed_messages


@router.delete("/conversations/{id}")
async def delete_conversation(request: Request, id: str) -> dict[str, str]:
    if not request.app.state.db:
        return {"status": "ok", "message": "Conversation deleted successfully"}
    async with request.app.state.db.session_factory() as session:
        result = await session.execute(
            select(DBConversation).where(DBConversation.id == id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        await session.delete(conversation)
        await session.commit()
        return {"status": "ok", "message": "Conversation deleted successfully"}

