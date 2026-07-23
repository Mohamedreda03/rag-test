import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Configure UTF-8 stdout
sys.stdout.reconfigure(encoding='utf-8')

db_url = "postgresql+asyncpg://rag_user:rag_password@localhost:5433/rag_db"

async def main():
    engine = create_async_engine(db_url)
    print("Querying documents table...")
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT id, job_id, filename, status, chunks_indexed, error_detail, created_at FROM documents ORDER BY created_at DESC"))
        rows = list(result)
        print(f"Total documents: {len(rows)}")
        for r in rows:
            print(f"ID: {r[0]} | Job: {r[1]} | File: {r[2]} | Status: {r[3]} | Chunks: {r[4]} | Error: {r[5]}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
