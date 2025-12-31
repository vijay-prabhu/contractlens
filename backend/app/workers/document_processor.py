"""Background document processing worker."""
import asyncio
import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.core.supabase import get_supabase_client
from app.models.document import Document, DocumentStatus
from app.services.extraction_service import ExtractionService
from app.services.chunking_service import ChunkingService

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Processes documents in the background."""

    def __init__(self):
        self.extraction_service = ExtractionService()
        self.chunking_service = ChunkingService()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def process_document(self, document_id: uuid.UUID) -> bool:
        """Process a single document through the pipeline.

        Args:
            document_id: UUID of the document to process

        Returns:
            True if processing succeeded, False otherwise
        """
        async with async_session_maker() as session:
            try:
                # Fetch document
                result = await session.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = result.scalar_one_or_none()

                if not document:
                    logger.error(f"Document {document_id} not found")
                    return False

                # Update status to processing
                await self._update_status(
                    session, document, DocumentStatus.PROCESSING, "Starting processing"
                )

                # Download file from storage (files are stored in uploads/ folder)
                supabase = get_supabase_client()
                storage_path = f"uploads/{document.filename}"
                file_content = await self._download_file(supabase, storage_path)

                if not file_content:
                    await self._update_status(
                        session, document, DocumentStatus.FAILED, "Failed to download file"
                    )
                    return False

                # Extract text
                await self._update_status(
                    session, document, DocumentStatus.EXTRACTING, "Extracting text"
                )

                try:
                    extraction_result = self.extraction_service.extract(
                        file_content, document.file_type
                    )
                except Exception as e:
                    logger.error(f"Extraction failed for {document_id}: {e}")
                    await self._update_status(
                        session, document, DocumentStatus.FAILED, f"Extraction failed: {str(e)}"
                    )
                    return False

                # Chunk text for embeddings
                chunks = self.chunking_service.chunk_for_contracts(
                    extraction_result.text,
                    document_metadata={
                        "document_id": str(document_id),
                        "filename": document.original_filename,
                    },
                )

                # Store extracted text and metadata
                document.extracted_text = extraction_result.text
                document.page_count = extraction_result.page_count
                document.chunk_count = len(chunks)
                document.word_count = len(extraction_result.text.split())
                document.status = DocumentStatus.COMPLETED.value
                document.status_message = f"Extracted {extraction_result.page_count} pages, {len(chunks)} chunks"

                await session.commit()
                logger.info(f"Document {document_id} processed successfully")
                return True

            except Exception as e:
                logger.exception(f"Error processing document {document_id}: {e}")
                await session.rollback()
                return False

    async def _update_status(
        self,
        session: AsyncSession,
        document: Document,
        status: DocumentStatus,
        message: str,
    ) -> None:
        """Update document status."""
        document.status = status.value
        document.status_message = message
        await session.commit()
        logger.info(f"Document {document.id} status: {status.value} - {message}")

    async def _download_file(self, supabase, filename: str) -> Optional[bytes]:
        """Download file from Supabase storage."""
        try:
            response = supabase.storage.from_("documents").download(filename)
            return response
        except Exception as e:
            logger.error(f"Failed to download {filename}: {e}")
            return None

    async def start_background_worker(self, poll_interval: int = 5) -> None:
        """Start background worker that polls for pending documents.

        Args:
            poll_interval: Seconds between polls for new documents
        """
        self._running = True
        logger.info("Document processor started")

        while self._running:
            try:
                async with async_session_maker() as session:
                    # Find documents waiting to be processed
                    result = await session.execute(
                        select(Document)
                        .where(Document.status == DocumentStatus.UPLOADED.value)
                        .order_by(Document.created_at)
                        .limit(1)
                    )
                    document = result.scalar_one_or_none()

                    if document:
                        logger.info(f"Processing document: {document.id}")
                        await self.process_document(document.id)

            except Exception as e:
                logger.exception(f"Worker error: {e}")

            await asyncio.sleep(poll_interval)

    def stop(self) -> None:
        """Stop the background worker."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Document processor stopped")


# Global processor instance
processor = DocumentProcessor()


async def start_processor() -> None:
    """Start the document processor as a background task."""
    processor._task = asyncio.create_task(processor.start_background_worker())


async def stop_processor() -> None:
    """Stop the document processor."""
    processor.stop()
