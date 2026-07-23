import sys
from qdrant_client import QdrantClient

sys.stdout.reconfigure(encoding='utf-8')

client = QdrantClient("http://localhost:6333")
collection_name = "rag_chunks_voyage"

try:
    points, _ = client.scroll(
        collection_name=collection_name,
        limit=100,
        with_payload=True,
        with_vectors=False
    )
    print(f"Total points scrolled: {len(points)}")
    for i, p in enumerate(points):
        payload = p.payload
        print(f"\n--- Point {i+1} ---")
        print(f"DocId: {payload.get('document_id')}")
        print(f"Source: {payload.get('source')}")
        child_text = payload.get('child_text', '')
        parent_text = payload.get('parent_text', '')
        print(f"Child Text Length: {len(child_text)} | Parent Text Length: {len(parent_text)}")
        print(f"Child Text snippet: {repr(child_text[:200])}")
        print(f"Parent Text snippet: {repr(parent_text[:200])}")
except Exception as e:
    print("Error:", e)
