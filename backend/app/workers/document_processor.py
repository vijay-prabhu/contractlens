"""Background document processing worker."""
import asyncio
import json
import logging
import time
import uuid
from typing import Optional, List

import sentry_sdk
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import async_session_maker
from app.core.supabase import get_supabase_client
from app.models.document import Document, DocumentStatus
from app.models.document_version import DocumentVersion
from app.models.clause import Clause
from app.services.extraction_service import ExtractionService
from app.services.chunking_service import ChunkingService, TextChunk
from app.services.embedding_service import EmbeddingService
from app.services.classification_service import ClassificationService, ClassificationResult

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Processes documents in the background."""

    def __init__(self):
        self.extraction_service = ExtractionService()
        self.chunking_service = ChunkingService()
        self.embedding_service = EmbeddingService()
        self.classification_service = ClassificationService()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def process_document(self, document_id: uuid.UUID) -> bool:
        """Process a single document through the pipeline.

        Args:
            document_id: UUID of the document to process

        Returns:
            True if processing succeeded, False otherwise
        """
        with sentry_sdk.start_transaction(op="worker.process_document", name="process_document") as transaction:
            transaction.set_tag("document_id", str(document_id))

            async with async_session_maker() as session:
                try:
                    pipeline_start = time.monotonic()
                    timings = {}

                    # Fetch document and version
                    with sentry_sdk.start_span(op="db.fetch", description="Fetch document and version"):
                        t0 = time.monotonic()
                        result = await session.execute(
                            select(Document).where(Document.id == document_id)
                        )
                        document = result.scalar_one_or_none()

                        if not document:
                            logger.error(f"Document {document_id} not found")
                            transaction.set_status("not_found")
                            return False

                        # Update status to processing
                        await self._update_status(
                            session, document, DocumentStatus.PROCESSING, "Starting processing"
                        )

                        # Get the latest version to process
                        version_result = await session.execute(
                            select(DocumentVersion)
                            .where(DocumentVersion.document_id == document_id)
                            .order_by(DocumentVersion.version_number.desc())
                            .limit(1)
                        )
                        document_version = version_result.scalar_one_or_none()

                        if not document_version:
                            logger.error(f"No document version found for {document_id}")
                            await self._update_status(
                                session, document, DocumentStatus.FAILED, "No document version found"
                            )
                            transaction.set_status("not_found")
                            return False
                        timings["db_fetch"] = time.monotonic() - t0

                    # Download file from storage using version's storage path
                    with sentry_sdk.start_span(op="storage.download", description="Download file from Supabase"):
                        t0 = time.monotonic()
                        supabase = get_supabase_client()
                        file_content = await self._download_file(supabase, document_version.storage_path)
                        timings["storage_download"] = time.monotonic() - t0

                        if not file_content:
                            await self._update_status(
                                session, document, DocumentStatus.FAILED, "Failed to download file"
                            )
                            transaction.set_status("internal_error")
                            return False

                    # Extract text
                    with sentry_sdk.start_span(op="extraction", description="Extract text from document"):
                        await self._update_status(
                            session, document, DocumentStatus.EXTRACTING, f"Extracting text (v{document_version.version_number})"
                        )

                        try:
                            t0 = time.monotonic()
                            extraction_result = self.extraction_service.extract(
                                file_content, document.file_type
                            )
                            timings["text_extraction"] = time.monotonic() - t0
                        except Exception as e:
                            logger.error(f"Extraction failed for {document_id}: {e}")
                            sentry_sdk.capture_exception(e)
                            await self._update_status(
                                session, document, DocumentStatus.FAILED, f"Extraction failed: {str(e)}"
                            )
                            transaction.set_status("internal_error")
                            return False

                    # Chunk text for embeddings
                    with sentry_sdk.start_span(op="chunking", description="Chunk text for embeddings"):
                        t0 = time.monotonic()
                        chunks = self.chunking_service.chunk_for_contracts(
                            extraction_result.text,
                            document_metadata={
                                "document_id": str(document_id),
                                "filename": document.original_filename,
                            },
                        )
                        timings["chunking"] = time.monotonic() - t0

                    # Generate embeddings and classify clauses
                    with sentry_sdk.start_span(op="ai.embed_and_classify", description="Embeddings + classification"):
                        # Update status to analyzing
                        await self._update_status(
                            session, document, DocumentStatus.ANALYZING, "Generating embeddings and classifying clauses"
                        )

                        # Update document version with extracted text
                        document_version.extracted_text = extraction_result.text
                        document_version.page_count = extraction_result.page_count
                        document_version.word_count = len(extraction_result.text.split())

                        # Generate embeddings and create clauses
                        t0 = time.monotonic()
                        clauses_created = await self._create_clauses_with_embeddings(
                            session, document_version.id, chunks
                        )
                        timings["ai_embed_and_classify"] = time.monotonic() - t0

                    # Save results
                    with sentry_sdk.start_span(op="db.save", description="Commit results to database"):
                        t0 = time.monotonic()
                        # Store extracted text and metadata on document
                        document.extracted_text = extraction_result.text
                        document.page_count = extraction_result.page_count
                        document.chunk_count = len(chunks)
                        document.word_count = len(extraction_result.text.split())
                        document.status = DocumentStatus.COMPLETED.value
                        document.status_message = f"Processed {extraction_result.page_count} pages, {clauses_created} clauses with embeddings"

                        await session.commit()
                        timings["db_save"] = time.monotonic() - t0

                    total = time.monotonic() - pipeline_start
                    timings["total"] = total
                    logger.info(
                        f"[PERF] Document {document_id} — {clauses_created} clauses, {len(chunks)} chunks\n"
                        f"  db_fetch:            {timings['db_fetch']:.2f}s\n"
                        f"  storage_download:    {timings['storage_download']:.2f}s\n"
                        f"  text_extraction:     {timings['text_extraction']:.2f}s\n"
                        f"  chunking:            {timings['chunking']:.2f}s\n"
                        f"  ai_embed+classify:   {timings['ai_embed_and_classify']:.2f}s\n"
                        f"  db_save:             {timings['db_save']:.2f}s\n"
                        f"  TOTAL:               {total:.2f}s"
                    )
                    transaction.set_status("ok")
                    return True

                except Exception as e:
                    logger.exception(f"Error processing document {document_id}: {e}")
                    sentry_sdk.set_context("document", {
                        "document_id": str(document_id),
                    })
                    sentry_sdk.capture_exception(e)
                    transaction.set_status("internal_error")
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
            sentry_sdk.set_context("storage", {"filename": filename})
            sentry_sdk.capture_exception(e)
            return None

    async def _create_clauses_with_embeddings(
        self,
        session: AsyncSession,
        document_version_id: uuid.UUID,
        chunks: List[TextChunk],
    ) -> int:
        """Create clause records with embeddings and classifications for each chunk.

        Args:
            session: Database session
            document_version_id: ID of the document version
            chunks: List of text chunks

        Returns:
            Number of clauses created
        """
        if not chunks:
            return 0

        # Extract text from chunks for batch processing
        chunk_texts = [chunk.content for chunk in chunks]

        # Generate embeddings in batch
        try:
            t0 = time.monotonic()
            embeddings = self.embedding_service.generate_embeddings(chunk_texts)
            logger.info(f"[PERF] Embeddings: {time.monotonic() - t0:.2f}s for {len(embeddings)} chunks")
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            sentry_sdk.set_context("embeddings", {"chunk_count": len(chunks)})
            sentry_sdk.capture_exception(e)
            embeddings = [None] * len(chunks)

        # Classify clauses using GPT-4o-mini (parallel)
        try:
            t0 = time.monotonic()
            classifications = await self.classification_service.classify_clauses_batch_async(chunk_texts)
            logger.info(f"[PERF] Classification: {time.monotonic() - t0:.2f}s for {len(classifications)} clauses (parallel API calls)")
        except Exception as e:
            logger.error(f"Failed to classify clauses: {e}")
            sentry_sdk.set_context("classification", {"chunk_count": len(chunks)})
            sentry_sdk.capture_exception(e)
            # Create default classifications on error
            from app.models.clause import ClauseType, RiskLevel
            classifications = [
                ClassificationResult(
                    clause_type=ClauseType.OTHER.value,
                    risk_level=RiskLevel.LOW.value,
                    risk_score=0.0,
                    risk_explanation="Classification unavailable",
                    confidence=0.0,
                    recommendations=[],
                )
                for _ in chunks
            ]

        # Create clause records with embeddings and classifications
        clauses_created = 0
        for chunk, embedding, classification in zip(chunks, embeddings, classifications):
            clause = Clause(
                text=chunk.content,
                clause_type=classification.clause_type,
                risk_level=classification.risk_level,
                risk_score=classification.risk_score,
                risk_explanation=classification.risk_explanation,
                recommendations=json.dumps(classification.recommendations) if classification.recommendations else None,
                start_position=chunk.start_char,
                end_position=chunk.end_char,
                embedding=embedding,
                document_version_id=document_version_id,
            )
            session.add(clause)
            clauses_created += 1

        # Log risk summary
        risk_summary = self.classification_service.calculate_document_risk_summary(classifications)
        logger.info(
            f"Created {clauses_created} clauses - "
            f"Risk: {risk_summary['overall_risk_level']} ({risk_summary['overall_risk_score']:.2f}), "
            f"Critical: {risk_summary['critical_clauses']}, High: {risk_summary['high_risk_clauses']}"
        )

        return clauses_created

    async def start_background_worker(self, poll_interval: int = 15) -> None:
        """Start background worker that polls for pending documents.

        Args:
            poll_interval: Seconds between polls for new documents (default 15s to reduce connection pressure)
        """
        self._running = True
        logger.info("Document processor started")

        while self._running:
            try:
                async with async_session_maker() as session:
                    # Find documents waiting to be processed:
                    # 1. Documents with 'uploaded' status (new uploads)
                    # 2. Documents stuck in intermediate states for > 2 minutes (failed/crashed processing)
                    stuck_threshold = datetime.now(timezone.utc) - timedelta(minutes=2)
                    intermediate_statuses = [
                        DocumentStatus.PROCESSING.value,
                        DocumentStatus.EXTRACTING.value,
                        DocumentStatus.ANALYZING.value,
                    ]
                    result = await session.execute(
                        select(Document)
                        .where(
                            or_(
                                Document.status == DocumentStatus.UPLOADED.value,
                                and_(
                                    Document.status.in_(intermediate_statuses),
                                    Document.updated_at < stuck_threshold
                                )
                            )
                        )
                        .order_by(Document.created_at)
                        .limit(1)
                    )
                    document = result.scalar_one_or_none()
                    # Explicitly close the result to release connection faster
                    await session.commit()

                    if document:
                        logger.info(f"Processing document: {document.id}")
                        await self.process_document(document.id)

            except Exception as e:
                logger.exception(f"Worker error: {e}")
                sentry_sdk.capture_exception(e)

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
