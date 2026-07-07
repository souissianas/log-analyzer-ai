"""
scripts/ingest_runbooks.py
One-shot script to embed and ingest all runbook Markdown files into ChromaDB.
Run this after the ChromaDB service is healthy.

Usage:
    python scripts/ingest_runbooks.py
    # or via docker:
    docker compose exec backend python scripts/ingest_runbooks.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add backend root to path when running as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.rag_service import add_runbook, ensure_collection

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

RUNBOOKS_DIR = Path(__file__).resolve().parent.parent / "runbooks"

# Map filename → category
CATEGORY_MAP = {
    "connection_errors": "connection",
    "memory_errors": "memory",
    "disk_errors": "disk",
    "auth_errors": "auth",
    "ssl_errors": "ssl",
    "general_errors": "general",
}


async def ingest_all():
    if not RUNBOOKS_DIR.exists():
        logger.error("Runbooks directory not found: %s", RUNBOOKS_DIR)
        sys.exit(1)

    logger.info("Ensuring ChromaDB collection exists…")
    ready = await ensure_collection()
    if not ready:
        logger.error("ChromaDB not available — aborting ingestion")
        sys.exit(1)

    md_files = sorted(RUNBOOKS_DIR.glob("*.md"))
    if not md_files:
        logger.warning("No runbook Markdown files found in %s", RUNBOOKS_DIR)
        return

    success = 0
    for md_file in md_files:
        stem = md_file.stem  # e.g. "connection_errors"
        category = CATEGORY_MAP.get(stem, "general")
        content = md_file.read_text(encoding="utf-8")

        # Split into chunks of ~800 chars for better retrieval granularity
        chunks = _chunk_text(content, max_chars=800)
        for i, chunk in enumerate(chunks):
            doc_id = f"{stem}_{i}"
            ok = await add_runbook(doc_id=doc_id, category=category, content=chunk)
            if ok:
                success += 1
                logger.info("  ✓ %s (chunk %d/%d)", stem, i + 1, len(chunks))
            else:
                logger.warning("  ✗ %s chunk %d failed", stem, i + 1)

    logger.info("Ingestion complete — %d chunks ingested from %d files", success, len(md_files))


def _chunk_text(text: str, max_chars: int = 800) -> list[str]:
    """Split text into chunks on paragraph boundaries."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}".strip() if current else para
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


if __name__ == "__main__":
    asyncio.run(ingest_all())
