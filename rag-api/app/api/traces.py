"""Trace inspection endpoints and the interactive token tracking dashboard."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.core.tracing import trace_store

router = APIRouter()
_DASHBOARD_PATH = Path(__file__).parent.parent / "templates" / "dashboard.html"


def _get_dashboard_html() -> str:
    if _DASHBOARD_PATH.exists():
        return _DASHBOARD_PATH.read_text(encoding="utf-8")
    return "<h1>Dashboard template not found</h1>"


@router.get("/traces")
async def list_traces() -> list[dict[str, Any]]:
    return trace_store.list_summaries()


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> dict[str, Any]:
    trace = trace_store.get(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Unknown trace id")
    return trace


@router.delete("/traces")
async def clear_traces() -> dict[str, str]:
    trace_store.clear()
    return {"status": "cleared"}


