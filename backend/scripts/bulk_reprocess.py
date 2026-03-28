"""Bulk re-process all documents through the current pipeline.

Runs every document through the latest extraction (Docling),
chunking (section-aware), embedding (text-embedding-3-large),
and classification (structured outputs) pipeline.

Usage:
    cd backend
    poetry run python scripts/bulk_reprocess.py
    poetry run python scripts/bulk_reprocess.py --dry-run  # List documents without processing
"""
import asyncio
import argparse
import logging
import sys
import time

sys.path.insert(0, ".")

from app.core.database import async_session_maker
from app.models.document import Document, DocumentStatus
from app.workers.document_processor import DocumentProcessor
from sqlalchemy import select, update

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("bulk_reprocess")


async def get_all_documents():
    """Fetch all completed or failed documents."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Document)
            .where(Document.status.in_([
                DocumentStatus.COMPLETED.value,
                DocumentStatus.FAILED.value,
            ]))
            .order_by(Document.created_at)
        )
        return list(result.scalars().all())


async def reset_document_status(document_id):
    """Reset document to 'uploaded' so the processor picks it up."""
    async with async_session_maker() as session:
        await session.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(status=DocumentStatus.UPLOADED.value, status_message="Queued for re-processing")
        )
        await session.commit()


async def main(dry_run: bool = False):
    documents = await get_all_documents()

    if not documents:
        logger.info("No documents to re-process")
        return

    logger.info(f"Found {len(documents)} documents to re-process")
    for doc in documents:
        logger.info(f"  {doc.id} | {doc.original_filename} | {doc.status} | {doc.chunk_count or 0} clauses")

    if dry_run:
        logger.info("Dry run — no changes made")
        return

    processor = DocumentProcessor()
    total_start = time.monotonic()
    success = 0
    failed = 0

    for i, doc in enumerate(documents):
        logger.info(f"\n[{i+1}/{len(documents)}] Processing: {doc.original_filename}")

        # Reset status so processor can pick it up
        await reset_document_status(doc.id)

        try:
            result = await processor.process_document(doc.id)
            if result:
                success += 1
                logger.info(f"  OK — {doc.original_filename}")
            else:
                failed += 1
                logger.error(f"  FAILED — {doc.original_filename}")
        except Exception as e:
            failed += 1
            logger.error(f"  ERROR — {doc.original_filename}: {e}")

    elapsed = time.monotonic() - total_start
    logger.info(f"\nBulk re-processing complete:")
    logger.info(f"  Total:   {len(documents)}")
    logger.info(f"  Success: {success}")
    logger.info(f"  Failed:  {failed}")
    logger.info(f"  Time:    {elapsed:.1f}s ({elapsed/len(documents):.1f}s per document)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk re-process all documents")
    parser.add_argument("--dry-run", action="store_true", help="List documents without processing")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
