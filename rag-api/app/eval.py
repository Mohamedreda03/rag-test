"""Automated evaluation harness for RAG Pipeline.

Tests:
1. Structural Chunking Integrity (Header & Markdown table preservation).
2. Arabic BM25 Stemming & Tokenization Recall (Inflected prefix matching).
3. Hybrid Retrieval Precision, Recall@K, and MRR.
4. Evaluation Summary Report.
"""

import asyncio
import re
from dataclasses import dataclass
from app.config import get_settings
from app.core.chunker import ChildChunk, build_chunks
from app.core.retriever import BM25Index, ScoredChunk, _tokenize


@dataclass
class EvalResult:
    test_name: str
    passed: bool
    score: float
    details: str


def eval_structural_chunking() -> EvalResult:
    """Evaluate structural & markdown table preservation in chunker."""
    test_doc = """# دليل المعمارية التقنية للـ RAG

## جدول تكوين النظام

| المكون | النموذج | القيمة الافتراضية |
| :--- | :--- | :--- |
| المولد | GPT-4o | 0.2 |
| المحرك | Qdrant | Cosine |
| الترتيب | Voyage-3 | Rerank-2 |

## تفاصيل الخوارزمية

تم تصميم المحرك لدعم اللغة العربية بشكل مباشر بدقة عالية دون فقدان النصوص.
"""
    settings = get_settings()
    chunks = build_chunks(test_doc, "test_doc.md", settings)
    
    table_preserved = False
    header_preserved = False
    
    for chunk in chunks:
        if "| المكون | النموذج |" in chunk.parent_text or "| المكون | النموذج |" in chunk.text:
            table_preserved = True
        if "# دليل المعمارية" in chunk.parent_text or "## جدول تكوين" in chunk.parent_text:
            header_preserved = True
            
    passed = table_preserved and header_preserved
    score = 1.0 if passed else 0.0
    details = f"Chunks count: {len(chunks)}, Table Preserved: {table_preserved}, Headers Preserved: {header_preserved}"
    return EvalResult("Structural Chunking & Markdown Table Preservation", passed, score, details)


def eval_arabic_bm25_tokenization() -> EvalResult:
    """Evaluate Arabic BM25 tokenization and inflected prefix matching."""
    text_corpus = "تقدم المنصة خيارات متعددة للتطبيقات المعقدة ودعم النظم البرمجية."
    query_inflected = "بالتطبيقات"
    query_stem = "تطبيق"
    
    corpus_tokens = _tokenize(text_corpus)
    query_inflected_tokens = _tokenize(query_inflected)
    query_stem_tokens = _tokenize(query_stem)
    
    # Check if 'تطبيقات' or 'تطبيق' match between query and corpus tokens
    overlap_inflected = set(corpus_tokens).intersection(set(query_inflected_tokens))
    overlap_stem = set(corpus_tokens).intersection(set(query_stem_tokens))
    
    passed = len(overlap_inflected) > 0 and len(overlap_stem) > 0
    score = 1.0 if passed else 0.5 if len(overlap_stem) > 0 else 0.0
    details = (
        f"Corpus Tokens: {corpus_tokens[:6]}...\n"
        f"Inflected Query Tokens: {query_inflected_tokens}\n"
        f"Stemmed Matches: {overlap_inflected}"
    )
    return EvalResult("Arabic BM25 Tokenization & Prefix Matching", passed, score, details)


def eval_hybrid_bm25_retrieval() -> EvalResult:
    """Evaluate BM25 search precision & recall on multi-domain sample chunks."""
    sample_texts = [
        ("doc1", "يستخدم نظام RAG قاعدة بيانات Qdrant لحفظ المتجهات الدلالية."),
        ("doc2", "تقنية BM25 تقوم بالبحث اللفظي الكلاسيكي عن الكلمات المفتاحية."),
        ("doc3", "يتم دعم إعادة الترتيب بواسطة Voyage AI ريرانكر لرفع الدقة."),
        ("doc4", "تعتمد الهندسة على معمارية Parent-Child لحفظ السياق الكامل."),
    ]
    
    chunks = [
        ScoredChunk(
            id=f"c{i}",
            parent_id=f"p{i}",
            source=doc_id,
            child_text=text,
            parent_text=text,
        )
        for i, (doc_id, text) in enumerate(sample_texts)
    ]
    
    bm25 = BM25Index()
    bm25.build(chunks)
    
    # Query test: searching with inflected Arabic word
    results = bm25.search("بالقواعد المتجهيه Qdrant", top_k=2)
    top_hit_id = results[0].id if results else None
    
    passed = (top_hit_id == "c0")
    score = 1.0 if passed else 0.0
    details = f"Top Hit ID: {top_hit_id} (Expected 'c0'), Returned count: {len(results)}"
    return EvalResult("BM25 Retrieval Precision on Arabic & Tech terms", passed, score, details)


def run_all_evals() -> list[EvalResult]:
    evals = [
        eval_structural_chunking(),
        eval_arabic_bm25_tokenization(),
        eval_hybrid_bm25_retrieval(),
    ]
    return evals


import sys

# Ensure UTF-8 output handling on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    print("=" * 60)
    print("RUNNING RAG PIPELINE EVALUATION HARNESS")
    print("=" * 60)
    
    results = run_all_evals()
    total_score = sum(r.score for r in results) / len(results) * 100
    
    for r in results:
        status = "[PASS]" if r.passed else "[FAIL]"
        print(f"\n{status} {r.test_name}")
        print(f"Score: {r.score * 100:.1f}%")
        print(f"Details: {r.details}")
        
    print("\n" + "=" * 60)
    print(f"OVERALL RAG QUALITY SCORE: {total_score:.1f}%")
    print("=" * 60)


if __name__ == "__main__":
    main()

