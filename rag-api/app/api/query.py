"""Query endpoints: full answer and SSE streaming."""

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.schemas import QueryRequest, QueryResponse

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(request: Request, body: QueryRequest) -> QueryResponse:
    return await request.app.state.pipeline.run(body.question, body.conversation_id)


@router.post("/query/stream")
async def query_stream(request: Request, body: QueryRequest) -> EventSourceResponse:
    return EventSourceResponse(
        request.app.state.pipeline.run_stream(body.question, body.conversation_id)
    )
