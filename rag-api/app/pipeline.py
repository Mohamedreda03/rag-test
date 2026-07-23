"""Single orchestrator wiring all RAG stages into one pipeline:

route -> decompose -> expand (+HyDE) -> hybrid retrieve -> grade/retry ->
rerank -> generate -> verify

Every stage is recorded on a Tracer: mirrored to logs and inspectable via the
/traces API and the /dashboard page.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator

from sqlalchemy import select

from app.config import Settings
from app.core.decomposer import QueryDecomposer
from app.core.embedder import Embedder
from app.core.generator import Generator, build_context_block
from app.core.grader import RetrievalGrader
from app.core.reranker import Reranker
from app.core.retriever import BM25Index, HybridRetriever, ScoredChunk, VectorStore
from app.core.router import QueryRouter, Route
from app.core.status import status_event
from app.core.tracing import Tracer, chunk_summaries, trace_store
from app.core.verifier import Verifier
from app.db import DBConversation, DBMessage
from app.llm import LLMClient, estimate_tokens
from app.schemas import QueryResponse, Source

_SOURCE_PREVIEW_CHARS = 500


class RAGPipeline:
    """End-to-end question answering over the indexed content."""

    def __init__(
        self,
        settings: Settings,
        llm: LLMClient,
        embedder: Embedder,
        store: VectorStore,
        bm25: BM25Index,
        db = None,
    ) -> None:
        self._settings = settings
        self._db = db
        self._router = QueryRouter(llm)
        self._decomposer = QueryDecomposer(llm, settings)
        self._retriever = HybridRetriever(embedder, store, bm25, settings)
        self._grader = RetrievalGrader(llm)
        if settings.reranker_provider == "voyage":
            from app.voyage import VoyageReranker
            self._reranker = VoyageReranker(settings)
        else:
            self._reranker = Reranker(llm)
        self._generator = Generator(llm)
        self._verifier = Verifier(llm)

    async def run(self, question: str, conversation_id: str | None = None) -> QueryResponse:
        tracer = Tracer(question)
        
        # Resolve conversation & save user message
        actual_conv_id = conversation_id
        if self._db:
            async with self._db.session_factory() as session:
                if not actual_conv_id:
                    conv = DBConversation(title=question[:50])
                    session.add(conv)
                    await session.commit()
                    await session.refresh(conv)
                    actual_conv_id = conv.id
                else:
                    conv_res = await session.execute(
                        select(DBConversation).where(DBConversation.id == actual_conv_id)
                    )
                    if not conv_res.scalar_one_or_none():
                        conv = DBConversation(id=actual_conv_id, title=question[:50])
                        session.add(conv)
                        await session.commit()
                        actual_conv_id = conv.id

                user_msg = DBMessage(
                    conversation_id=actual_conv_id,
                    role="user",
                    content=question,
                )
                session.add(user_msg)
                await session.commit()

        route, sub_questions = await self._route_and_decompose(question, tracer)
        merged = await self._retrieve_all(sub_questions, route.use_hyde, tracer)
        chunks = await self._rerank_step(question, merged, tracer)
        context = build_context_block(chunks)
        started = time.perf_counter()
        draft = await self._generator.generate(question, sub_questions, context)
        gen_p_tok = estimate_tokens(question + context)
        gen_c_tok = estimate_tokens(draft)
        tracer.add_step(
            "generation",
            {"draft_answer": draft},
            started=started,
            tokens={"prompt_tokens": gen_p_tok, "completion_tokens": gen_c_tok, "total_tokens": gen_p_tok + gen_c_tok},
        )
        started = time.perf_counter()
        answer, verified = await self._verifier.finalize(question, context, draft)
        ver_p_tok = estimate_tokens(question + context + draft)
        ver_c_tok = estimate_tokens(answer)
        tracer.add_step(
            "verification",
            {"verified": verified, "revised": answer != draft, "final_answer": answer},
            started=started,
            tokens={"prompt_tokens": ver_p_tok, "completion_tokens": ver_c_tok, "total_tokens": ver_p_tok + ver_c_tok},
        )
        tracer.finish(answer, verified)
        trace_store.add(tracer)


        sources = self._to_sources(chunks)

        if self._db and actual_conv_id:
            async with self._db.session_factory() as session:
                assistant_msg = DBMessage(
                    conversation_id=actual_conv_id,
                    role="assistant",
                    content=answer,
                    status="done",
                    sources=json.dumps([s.model_dump() for s in sources], ensure_ascii=False),
                    trace_id=tracer.id,
                )
                session.add(assistant_msg)
                await session.commit()

        return QueryResponse(
            answer=answer,
            question_type=route.type,
            sub_questions=sub_questions,
            sources=sources,
            verified=verified,
            trace_id=tracer.id,
            conversation_id=actual_conv_id,
        )

    async def run_stream(self, question: str, conversation_id: str | None = None) -> AsyncIterator[dict[str, str]]:
        """SSE event stream: 'status' progress events for each pipeline stage,
        then one 'meta' event, then 'token' events, then 'done'.

        Status messages are user-facing Egyptian Arabic and adapt to the
        detected question type. The verification stage is skipped in streaming
        mode because the answer is emitted incrementally.
        """
        tracer = Tracer(question)
        
        # Resolve conversation & save user message
        actual_conv_id = conversation_id
        if self._db:
            async with self._db.session_factory() as session:
                if not actual_conv_id:
                    conv = DBConversation(title=question[:50])
                    session.add(conv)
                    await session.commit()
                    await session.refresh(conv)
                    actual_conv_id = conv.id
                else:
                    conv_res = await session.execute(
                        select(DBConversation).where(DBConversation.id == actual_conv_id)
                    )
                    if not conv_res.scalar_one_or_none():
                        conv = DBConversation(id=actual_conv_id, title=question[:50])
                        session.add(conv)
                        await session.commit()
                        actual_conv_id = conv.id

                user_msg = DBMessage(
                    conversation_id=actual_conv_id,
                    role="user",
                    content=question,
                )
                session.add(user_msg)
                await session.commit()

        yield status_event("understanding")
        route, sub_questions = await self._route_and_decompose(question, tracer)
        yield status_event("searching", question_type=route.type, sub_count=len(sub_questions))
        merged = await self._retrieve_all(sub_questions, route.use_hyde, tracer)
        yield status_event("ranking")
        chunks = await self._rerank_step(question, merged, tracer)
        yield status_event("generating")
        context = build_context_block(chunks)
        
        sources = self._to_sources(chunks)
        meta = {
            "question_type": route.type,
            "sub_questions": sub_questions,
            "sources": [source.model_dump() for source in sources],
            "trace_id": tracer.id,
            "conversation_id": actual_conv_id,
        }
        yield {"event": "meta", "data": json.dumps(meta, ensure_ascii=False)}
        
        buffer: list[str] = []
        async for token in self._generator.stream(question, sub_questions, context):
            buffer.append(token)
            yield {"event": "token", "data": token}
        answer = "".join(buffer)
        try:
            gen_p_tok = estimate_tokens(question + context)
            gen_c_tok = estimate_tokens(answer)
            tracer.add_step(
                "generation",
                {"answer": answer},
                tokens={"prompt_tokens": gen_p_tok, "completion_tokens": gen_c_tok, "total_tokens": gen_p_tok + gen_c_tok},
            )
            tracer.finish(answer)
            trace_store.add(tracer)
        except Exception:
            pass


        if self._db and actual_conv_id:
            async with self._db.session_factory() as session:
                assistant_msg = DBMessage(
                    conversation_id=actual_conv_id,
                    role="assistant",
                    content=answer,
                    status="done",
                    sources=json.dumps([s.model_dump() for s in sources], ensure_ascii=False),
                    trace_id=tracer.id,
                )
                session.add(assistant_msg)
                await session.commit()

        yield {"event": "done", "data": ""}

    async def _route_and_decompose(
        self, question: str, tracer: Tracer
    ) -> tuple[Route, list[str]]:
        started = time.perf_counter()
        route = await self._router.classify(question)
        tracer.add_step(
            "routing",
            {"question_type": route.type, "use_hyde": route.use_hyde},
            input={"question": question},
            started=started,
        )
        started = time.perf_counter()
        if route.type == "simple":
            sub_questions = [question]
        else:
            sub_questions = await self._decomposer.decompose(question)
        tracer.add_step("decomposition", {"sub_questions": sub_questions}, started=started)
        return route, sub_questions

    async def _retrieve_all(
        self, sub_questions: list[str], use_hyde: bool, tracer: Tracer
    ) -> list[ScoredChunk]:
        chunk_lists = await asyncio.gather(
            *(self._retrieve_for(sq, use_hyde, tracer) for sq in sub_questions)
        )
        merged = self._retriever.merge(chunk_lists)
        tracer.add_step(
            "merge",
            {"candidate_count": len(merged), "candidates": chunk_summaries(merged)},
        )
        return merged

    async def _rerank_step(
        self, question: str, merged: list[ScoredChunk], tracer: Tracer
    ) -> list[ScoredChunk]:
        started = time.perf_counter()
        chunks = await self._reranker.rerank(question, merged, self._settings.rerank_top_n)
        tracer.add_step("reranking", {"selected": chunk_summaries(chunks)}, started=started)
        return chunks

    async def _retrieve_for(
        self, sub_question: str, use_hyde: bool, tracer: Tracer
    ) -> list[ScoredChunk]:
        """Retrieve for one sub-question with expansion, HyDE, and CRAG-style retry."""
        started = time.perf_counter()
        expansions = await self._decomposer.expand(sub_question)
        queries = [sub_question, *expansions]
        hyde_passage = None
        if use_hyde:
            hyde_passage = await self._decomposer.hyde(sub_question)
            if hyde_passage:
                queries.append(hyde_passage)
        chunks = await self._retriever.retrieve_many(queries)
        grade = await self._grader.grade(sub_question, chunks)
        rewritten_queries: list[str] = []
        retries = 0
        while not grade.sufficient and retries < self._settings.max_retrieval_retries:
            rewritten_queries.append(grade.rewritten_query)
            extra = await self._retriever.retrieve_many([grade.rewritten_query])
            chunks = self._retriever.merge([chunks, extra])
            grade = await self._grader.grade(sub_question, chunks)
            retries += 1
        tracer.add_step(
            "retrieval",
            {
                "expanded_queries": expansions,
                "hyde_passage": hyde_passage,
                "grader_sufficient": grade.sufficient,
                "rewritten_queries": rewritten_queries,
                "retrieved_count": len(chunks),
                "retrieved": chunk_summaries(chunks[:10]),
            },
            input={"sub_question": sub_question},
            started=started,
        )
        return chunks

    @staticmethod
    def _to_sources(chunks: list[ScoredChunk]) -> list[Source]:
        return [
            Source(
                ref=i + 1,
                source=chunk.source,
                text=chunk.parent_text[:_SOURCE_PREVIEW_CHARS],
                score=round(chunk.score, 4),
            )
            for i, chunk in enumerate(chunks)
        ]
