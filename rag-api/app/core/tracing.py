"""Pipeline tracing with per-step token metrics, JSON file persistence, and analytics API."""

import json
import logging
import os
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("rag.pipeline")

_LOG_PREVIEW_CHARS = 400
_CHUNK_PREVIEW_CHARS = 200
_JSON_STORE_PATH = Path("data/traces.json")


def chunk_summaries(chunks: list[Any]) -> list[dict[str, Any]]:
    """Compact JSON-friendly view of retrieved chunks."""
    return [
        {
            "source": chunk.source,
            "score": round(chunk.score, 4),
            "preview": chunk.parent_text[:_CHUNK_PREVIEW_CHARS],
        }
        for chunk in chunks
    ]


class Tracer:
    """Collects step records and precise token metrics for a single question run."""

    def __init__(self, question: str) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.question = question
        self.created_at = datetime.now(timezone.utc)
        self.steps: list[dict[str, Any]] = []
        self.answer: str | None = None
        self.verified: bool | None = None
        self.duration_ms: float | None = None
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0
        self._started = time.perf_counter()
        logger.info("trace=%s started question=%r", self.id, question)

    def add_step(
        self,
        name: str,
        output: Any,
        *,
        input: Any = None,
        started: float | None = None,
        tokens: dict[str, int] | None = None,
    ) -> None:
        duration_ms = (
            round((time.perf_counter() - started) * 1000, 1) if started is not None else None
        )
        step_entry: dict[str, Any] = {
            "name": name,
            "duration_ms": duration_ms,
            "input": input,
            "output": output,
        }

        if tokens:
            p_tok = tokens.get("prompt_tokens", 0)
            c_tok = tokens.get("completion_tokens", 0)
            t_tok = tokens.get("total_tokens", p_tok + c_tok)
            step_entry["tokens"] = {
                "prompt_tokens": p_tok,
                "completion_tokens": c_tok,
                "total_tokens": t_tok,
            }
            self.prompt_tokens += p_tok
            self.completion_tokens += c_tok
            self.total_tokens += t_tok

        self.steps.append(step_entry)
        preview = json.dumps(output, ensure_ascii=False, default=str)[:_LOG_PREVIEW_CHARS]
        logger.info(
            "trace=%s step=%s duration_ms=%s output=%s", self.id, name, duration_ms, preview
        )

    def finish(self, answer: str, verified: bool | None = None) -> None:
        self.answer = answer
        self.verified = verified
        self.duration_ms = round((time.perf_counter() - self._started) * 1000, 1)
        logger.info(
            "trace=%s finished duration_ms=%s verified=%s total_tokens=%s",
            self.id,
            self.duration_ms,
            verified,
            self.total_tokens,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "created_at": self.created_at.isoformat(),
            "duration_ms": self.duration_ms,
            "verified": self.verified,
            "answer": self.answer,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "steps": self.steps,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "created_at": self.created_at.isoformat(),
            "duration_ms": self.duration_ms,
            "step_count": len(self.steps),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


class TraceStore:
    """Persistent JSON file & in-memory store for pipeline traces."""

    def __init__(self, max_traces: int = 500, json_file: Path = _JSON_STORE_PATH) -> None:
        self._traces: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._max_traces = max_traces
        self._json_file = json_file
        self._load_from_json()

    def _load_from_json(self) -> None:
        try:
            if self._json_file.exists():
                with open(self._json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        self._traces[item["id"]] = item
                logger.info("Loaded %d traces from %s", len(self._traces), self._json_file)
        except Exception as e:
            logger.warning("Failed to load traces from JSON: %s", e)

    def _save_to_json(self) -> None:
        try:
            self._json_file.parent.mkdir(parents=True, exist_ok=True)
            data = list(self._traces.values())
            with open(self._json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning("Failed to save traces to JSON: %s", e)

    def add(self, tracer: Tracer) -> None:
        try:
            self._traces[tracer.id] = tracer.to_dict()
            while len(self._traces) > self._max_traces:
                self._traces.popitem(last=False)
            self._save_to_json()
        except Exception as e:
            logger.warning("Failed to record trace %s: %s", getattr(tracer, "id", "unknown"), e)

    def get(self, trace_id: str) -> dict[str, Any] | None:
        return self._traces.get(trace_id)

    def list_summaries(self) -> list[dict[str, Any]]:
        summaries = []
        try:
            for t in reversed(self._traces.values()):
                summaries.append({
                    "id": t["id"],
                    "question": t["question"],
                    "created_at": t.get("created_at"),
                    "duration_ms": t.get("duration_ms"),
                    "step_count": len(t.get("steps", [])),
                    "prompt_tokens": t.get("prompt_tokens", 0),
                    "completion_tokens": t.get("completion_tokens", 0),
                    "total_tokens": t.get("total_tokens", 0),
                    "verified": t.get("verified"),
                })
        except Exception as e:
            logger.warning("Failed to list trace summaries: %s", e)
        return summaries

    def clear(self) -> None:
        try:
            self._traces.clear()
            self._save_to_json()
        except Exception as e:
            logger.warning("Failed to clear trace store: %s", e)


trace_store = TraceStore()


