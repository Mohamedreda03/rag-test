"""Ingestion endpoints: upload documents and track indexing jobs."""

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile
from sqlalchemy import select

from app.core.chunker import ChildChunk, build_chunks, extract_text
from app.db import DBFolderDocument
from app.llm import LLMClient
from app.prompts import CONTEXTUAL_ENRICHMENT_PROMPT
from app.schemas import IngestAccepted, IngestStatus, DocumentResponse

_IN_MEMORY_JOBS: dict[str, dict[str, Any]] = {}
router = APIRouter()


@router.post("/ingest", response_model=IngestAccepted, status_code=202)

async def ingest(
    request: Request,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
) -> IngestAccepted:
    job_id = uuid.uuid4().hex
    payloads = []
    filenames = []
    
    _IN_MEMORY_JOBS[job_id] = {
        "status": "processing",
        "chunks_indexed": 0,
        "detail": None,
    }
    
    if request.app.state.db:
        async with request.app.state.db.session_factory() as session:
            for file in files:
                filename = file.filename or "unnamed"
                filenames.append(filename)
                data = await file.read()
                
                doc = DBFolderDocument(
                    job_id=job_id,
                    filename=filename,
                    status="processing",
                    chunks_indexed=0,
                )
                session.add(doc)
                await session.commit()
                await session.refresh(doc)
                
                payloads.append((doc.id, filename, data))
    else:
        for file in files:
            filename = file.filename or "unnamed"
            filenames.append(filename)
            data = await file.read()
            doc_id = uuid.uuid4().hex
            payloads.append((doc_id, filename, data))
            
    background_tasks.add_task(_process_job, request.app.state, job_id, payloads)
    return IngestAccepted(job_id=job_id, filenames=filenames)


@router.get("/ingest/status/{job_id}", response_model=IngestStatus)
async def ingest_status(request: Request, job_id: str) -> IngestStatus:
    if not request.app.state.db:
        job = _IN_MEMORY_JOBS.get(job_id, {"status": "processing", "chunks_indexed": 0, "detail": None})
        return IngestStatus(
            job_id=job_id,
            status=job.get("status", "processing"),
            detail=job.get("detail"),
            chunks_indexed=job.get("chunks_indexed", 0),
        )
    async with request.app.state.db.session_factory() as session:
        result = await session.execute(
            select(DBFolderDocument).where(DBFolderDocument.job_id == job_id)
        )
        docs = result.scalars().all()
        if not docs:
            raise HTTPException(status_code=404, detail="Unknown job id")
        
        statuses = [d.status for d in docs]
        total_chunks = sum(d.chunks_indexed for d in docs)
        
        if "processing" in statuses:
            status = "processing"
            detail = None
        elif "failed" in statuses:
            status = "failed"
            detail = "; ".join([d.error_detail for d in docs if d.error_detail]) or "Failed"
        else:
            status = "done"
            detail = None
            
        return IngestStatus(
            job_id=job_id,
            status=status,
            detail=detail,
            chunks_indexed=total_chunks,
        )



@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(request: Request) -> list[DocumentResponse]:
    if not request.app.state.db:
        # Direct Qdrant fallback when DB is offline
        chunks = await request.app.state.store.scroll_all()
        doc_map: dict[str, DocumentResponse] = {}
        for c in chunks:
            doc_id = c.document_id or c.source
            if doc_id not in doc_map:
                from datetime import datetime, timezone
                doc_map[doc_id] = DocumentResponse(
                    id=doc_id,
                    filename=c.source,
                    status="done",
                    chunks_indexed=1,
                    error_detail=None,
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )

            else:
                doc_map[doc_id].chunks_indexed += 1
        return list(doc_map.values())
        
    async with request.app.state.db.session_factory() as session:
        result = await session.execute(
            select(DBFolderDocument).order_by(DBFolderDocument.created_at.desc())
        )
        docs = result.scalars().all()
        return docs


@router.delete("/documents/{id}")
async def delete_document(request: Request, id: str) -> dict[str, str]:
    # Delete from Qdrant
    await request.app.state.store.delete_document(id)
    
    if request.app.state.db:
        async with request.app.state.db.session_factory() as session:
            result = await session.execute(
                select(DBFolderDocument).where(DBFolderDocument.id == id)
            )
            doc = result.scalar_one_or_none()
            if doc:
                await session.delete(doc)
                await session.commit()
                
    # Rebuild BM25 index
    request.app.state.bm25.build(await request.app.state.store.scroll_all())
    return {"status": "ok", "message": f"Document {id} deleted successfully"}



async def _process_job(state, job_id: str, payloads: list[tuple[str, str, bytes]]) -> None:
    settings = state.settings
    session_factory = state.db.session_factory if state.db else None
    total_indexed = 0
    
    for doc_id, filename, data in payloads:
        try:
            suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
            if suffix in {"jpg", "jpeg", "png"}:
                text = await _extract_image_ocr(state.vision_llm, data, suffix)
            elif suffix == "pdf":
                import io
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(data))
                is_scanned = True
                if len(reader.pages) > 0:
                    empty_or_short_pages = 0
                    total_chars = 0
                    for page in reader.pages:
                        page_text = (page.extract_text() or "").strip()
                        total_chars += len(page_text)
                        if len(page_text) < 150:
                            empty_or_short_pages += 1
                    avg_chars = total_chars / len(reader.pages)
                    short_pages_ratio = empty_or_short_pages / len(reader.pages)
                    is_scanned = avg_chars < 200 or short_pages_ratio > 0.6
                
                if is_scanned:
                    text = await _extract_scanned_pdf(state.vision_llm, data, job_id=job_id, concurrency=4)

                    # If OCR failed or hit quota, attempt fallback to direct text extraction
                    if not text.strip():
                        import io
                        from pypdf import PdfReader
                        reader = PdfReader(io.BytesIO(data))
                        extracted_fallback = "\n\n".join((page.extract_text() or "") for page in reader.pages)
                        if extracted_fallback.strip():
                            text = extracted_fallback
                else:
                    text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
            else:
                text = extract_text(filename, data)

            chunks = build_chunks(text, source=filename, settings=settings, document_id=doc_id)
            if not chunks:
                err_msg = f"No text could be extracted from '{filename}'. Check if the PDF is image-only or if Gemini Vision OCR quota is exceeded."
                if job_id in _IN_MEMORY_JOBS:
                    _IN_MEMORY_JOBS[job_id]["status"] = "failed"
                    _IN_MEMORY_JOBS[job_id]["detail"] = err_msg
                if session_factory:
                    async with session_factory() as session:
                        result = await session.execute(
                            select(DBFolderDocument).where(DBFolderDocument.id == doc_id)
                        )
                        doc = result.scalar_one_or_none()
                        if doc:
                            doc.status = "failed"
                            doc.error_detail = err_msg
                            await session.commit()
                continue

                
            if settings.enable_contextual_enrichment:
                await _enrich(state.llm, chunks, settings.enrichment_concurrency)
                
            vectors = await state.embedder.embed([chunk.index_text for chunk in chunks])
            await state.store.upsert(chunks, vectors)
            
            total_indexed += len(chunks)
            if job_id in _IN_MEMORY_JOBS:
                _IN_MEMORY_JOBS[job_id]["chunks_indexed"] = total_indexed
            
            if session_factory:
                async with session_factory() as session:
                    result = await session.execute(
                        select(DBFolderDocument).where(DBFolderDocument.id == doc_id)
                    )
                    doc = result.scalar_one_or_none()
                    if doc:
                        doc.status = "done"
                        doc.chunks_indexed = len(chunks)
                        await session.commit()
        except Exception as exc:
            import logging
            logging.getLogger("rag.pipeline").error(f"Error processing job file {filename}: {exc}", exc_info=True)
            if job_id in _IN_MEMORY_JOBS:
                _IN_MEMORY_JOBS[job_id]["status"] = "failed"
                _IN_MEMORY_JOBS[job_id]["detail"] = str(exc)
            if session_factory:
                async with session_factory() as session:
                    result = await session.execute(
                        select(DBFolderDocument).where(DBFolderDocument.id == doc_id)
                    )
                    doc = result.scalar_one_or_none()
                    if doc:
                        doc.status = "failed"
                        doc.error_detail = str(exc)
                        await session.commit()

    if job_id in _IN_MEMORY_JOBS and _IN_MEMORY_JOBS[job_id]["status"] != "failed":
        _IN_MEMORY_JOBS[job_id]["status"] = "done"
        _IN_MEMORY_JOBS[job_id]["chunks_indexed"] = total_indexed

    # Rebuild BM25 index once
    await state.store.ensure_collection()
    state.bm25.build(await state.store.scroll_all())



async def _extract_image_ocr(vision_llm, data: bytes, suffix: str) -> str:
    mime_type = f"image/{suffix}"
    if suffix == "jpg":
        mime_type = "image/jpeg"
    prompt = (
        "Extract all readable text from this document page. Output ONLY the extracted text. "
        "Do not add explanations, summaries, or metadata. Preserve Arabic text carefully."
    )
    return await vision_llm.complete_vision(prompt, data, mime_type)


async def _extract_scanned_pdf(vision_llm, data: bytes, job_id: str | None = None, concurrency: int = 4) -> str:
    import fitz  # PyMuPDF
    import re
    import logging

    doc = fitz.open(stream=data, filetype="pdf")
    pages = []
    total_pages = len(doc)
    
    for page_num in range(total_pages):
        page = doc.load_page(page_num)
        # Render page and downscale if larger than 1000px to optimize OCR speed
        pix = page.get_pixmap(dpi=150)
        if pix.width > 1000 or pix.height > 1000:
            scale = 1000 / max(pix.width, pix.height)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
        pages.append(pix.tobytes("jpeg"))

    semaphore = asyncio.Semaphore(concurrency)
    completed_count = 0
    results: list[tuple[int, str]] = []

    async def process_page(img_bytes: bytes, page_idx: int) -> tuple[int, str]:
        nonlocal completed_count
        async with semaphore:
            prompt = (
                "Extract all readable text from this document page. Output ONLY the extracted text. "
                "Do not add explanations, summaries, or metadata. Preserve Arabic text carefully."
            )
            max_retries = 6
            page_text = ""
            for attempt in range(max_retries):
                try:
                    text = await vision_llm.complete_vision(prompt, img_bytes, "image/jpeg")
                    text_str = (text or "").strip()
                    if text_str:
                        page_text = f"\n\n--- Page {page_idx + 1} ---\n\n" + text_str
                    break
                except Exception as e:
                    err_msg = str(e).lower()
                    is_rate_limit = any(
                        x in err_msg
                        for x in ["429", "rate limit", "quota", "resource exhausted", "limit exceeded"]
                    )
                    if is_rate_limit and attempt < max_retries - 1:
                        match = re.search(r"retrydelay['\":\s]+'?(\d+)", err_msg)
                        sleep_time = int(match.group(1)) + 2 if match else (2**attempt) + 3
                        logging.getLogger("rag.pipeline").warning(
                            f"Rate limit on page {page_idx + 1}/{total_pages}. Attempt {attempt + 1}/{max_retries}. Waiting {sleep_time}s..."
                        )
                        await asyncio.sleep(sleep_time)
                        continue
                    else:
                        logging.getLogger("rag.pipeline").error(
                            f"Error on page {page_idx + 1}/{total_pages}: {e}"
                        )
                        break
            
            completed_count += 1
            progress_msg = f"جاري قراءة الصفحة {completed_count} من إجمالي {total_pages} صفحة"
            logging.getLogger("rag.pipeline").info(f"[{completed_count}/{total_pages}] Page {page_idx + 1} done.")
            
            if job_id and job_id in _IN_MEMORY_JOBS:
                _IN_MEMORY_JOBS[job_id]["detail"] = progress_msg

            return (page_idx, page_text)

    page_results = await asyncio.gather(*(process_page(img, i) for i, img in enumerate(pages)))
    # Sort results by original page order
    sorted_results = sorted(page_results, key=lambda x: x[0])
    return "\n\n".join(res[1] for res in sorted_results if res[1])




async def _enrich(llm: LLMClient, chunks: list[ChildChunk], concurrency: int) -> None:
    """Prepend an LLM-generated contextual summary to each chunk (best effort)."""
    semaphore = asyncio.Semaphore(concurrency)

    async def enrich_one(chunk: ChildChunk) -> None:
        async with semaphore:
            try:
                chunk.context = (
                    await llm.complete(
                        CONTEXTUAL_ENRICHMENT_PROMPT,
                        f"<document>\n{chunk.parent_text[:6000]}\n</document>\n\n"
                        f"<chunk>\n{chunk.text}\n</chunk>",
                        small=True,
                    )
                ).strip()
            except Exception:
                chunk.context = ""

    await asyncio.gather(*(enrich_one(chunk) for chunk in chunks))
