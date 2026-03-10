"""Natural language query API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.database import get_session
from atlas_intel.llm.client import LLMUnavailableError
from atlas_intel.schemas.report import QueryRequest, QueryResponse

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def natural_language_query(
    request: QueryRequest,
    session: AsyncSession = Depends(get_session),
) -> QueryResponse:
    """Answer a natural language question about companies and markets."""
    from atlas_intel.services.query_service import process_natural_language_query

    try:
        return await process_natural_language_query(session, request.query)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/query/stream")
async def natural_language_query_stream(
    request: QueryRequest,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Stream a natural language query response via SSE."""
    from atlas_intel.services.query_service import stream_natural_language_query

    try:
        return StreamingResponse(
            stream_natural_language_query(session, request.query),
            media_type="text/event-stream",
        )
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
