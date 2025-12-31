"""Semantic search service using pgvector."""
import logging
from typing import List, Optional
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clause import Clause
from app.models.document_version import DocumentVersion
from app.models.document import Document
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A search result with similarity score."""
    clause_id: UUID
    text: str
    clause_type: str
    risk_level: str
    similarity: float
    document_id: UUID
    document_name: str


class SearchService:
    """Service for semantic search using embeddings."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_service = EmbeddingService()

    async def search_clauses(
        self,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.5,
        document_id: Optional[UUID] = None,
    ) -> List[SearchResult]:
        """Search for clauses semantically similar to the query.

        Args:
            query: Search query text
            limit: Maximum number of results
            min_similarity: Minimum cosine similarity threshold (0 to 1)
            document_id: Optional filter by specific document

        Returns:
            List of SearchResult objects sorted by similarity
        """
        # Generate embedding for query
        try:
            query_embedding = self.embedding_service.generate_embedding(query)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            return []

        # Build pgvector similarity search query
        # Using cosine distance: 1 - (embedding <=> query_embedding)
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        if document_id:
            sql = text("""
                SELECT
                    c.id,
                    c.text,
                    c.clause_type,
                    c.risk_level,
                    1 - (c.embedding <=> cast(:embedding as vector)) as similarity,
                    d.id as document_id,
                    d.original_filename as document_name
                FROM clauses c
                JOIN document_versions dv ON c.document_version_id = dv.id
                JOIN documents d ON dv.document_id = d.id
                WHERE c.embedding IS NOT NULL
                    AND d.id = cast(:document_id as uuid)
                    AND 1 - (c.embedding <=> cast(:embedding as vector)) >= :min_similarity
                ORDER BY c.embedding <=> cast(:embedding as vector)
                LIMIT :limit
            """)
            result = await self.db.execute(
                sql,
                {
                    "embedding": embedding_str,
                    "document_id": str(document_id),
                    "min_similarity": min_similarity,
                    "limit": limit,
                },
            )
        else:
            sql = text("""
                SELECT
                    c.id,
                    c.text,
                    c.clause_type,
                    c.risk_level,
                    1 - (c.embedding <=> cast(:embedding as vector)) as similarity,
                    d.id as document_id,
                    d.original_filename as document_name
                FROM clauses c
                JOIN document_versions dv ON c.document_version_id = dv.id
                JOIN documents d ON dv.document_id = d.id
                WHERE c.embedding IS NOT NULL
                    AND 1 - (c.embedding <=> cast(:embedding as vector)) >= :min_similarity
                ORDER BY c.embedding <=> cast(:embedding as vector)
                LIMIT :limit
            """)
            result = await self.db.execute(
                sql,
                {
                    "embedding": embedding_str,
                    "min_similarity": min_similarity,
                    "limit": limit,
                },
            )

        rows = result.fetchall()

        return [
            SearchResult(
                clause_id=row.id,
                text=row.text,
                clause_type=row.clause_type,
                risk_level=row.risk_level,
                similarity=float(row.similarity),
                document_id=row.document_id,
                document_name=row.document_name,
            )
            for row in rows
        ]

    async def find_similar_clauses(
        self,
        clause_id: UUID,
        limit: int = 5,
        min_similarity: float = 0.7,
        exclude_same_document: bool = True,
    ) -> List[SearchResult]:
        """Find clauses similar to a given clause.

        Args:
            clause_id: ID of the source clause
            limit: Maximum number of results
            min_similarity: Minimum cosine similarity threshold
            exclude_same_document: Whether to exclude clauses from same document

        Returns:
            List of similar clauses
        """
        # Get the source clause embedding
        result = await self.db.execute(
            select(Clause).where(Clause.id == clause_id)
        )
        source_clause = result.scalar_one_or_none()

        if not source_clause or source_clause.embedding is None:
            return []

        embedding_str = "[" + ",".join(str(x) for x in source_clause.embedding) + "]"

        if exclude_same_document:
            # Get the document ID for exclusion
            version_result = await self.db.execute(
                select(DocumentVersion).where(
                    DocumentVersion.id == source_clause.document_version_id
                )
            )
            source_version = version_result.scalar_one_or_none()
            source_document_id = source_version.document_id if source_version else None

            sql = text("""
                SELECT
                    c.id,
                    c.text,
                    c.clause_type,
                    c.risk_level,
                    1 - (c.embedding <=> cast(:embedding as vector)) as similarity,
                    d.id as document_id,
                    d.original_filename as document_name
                FROM clauses c
                JOIN document_versions dv ON c.document_version_id = dv.id
                JOIN documents d ON dv.document_id = d.id
                WHERE c.embedding IS NOT NULL
                    AND c.id != cast(:clause_id as uuid)
                    AND d.id != cast(:exclude_document_id as uuid)
                    AND 1 - (c.embedding <=> cast(:embedding as vector)) >= :min_similarity
                ORDER BY c.embedding <=> cast(:embedding as vector)
                LIMIT :limit
            """)
            result = await self.db.execute(
                sql,
                {
                    "embedding": embedding_str,
                    "clause_id": str(clause_id),
                    "exclude_document_id": str(source_document_id),
                    "min_similarity": min_similarity,
                    "limit": limit,
                },
            )
        else:
            sql = text("""
                SELECT
                    c.id,
                    c.text,
                    c.clause_type,
                    c.risk_level,
                    1 - (c.embedding <=> cast(:embedding as vector)) as similarity,
                    d.id as document_id,
                    d.original_filename as document_name
                FROM clauses c
                JOIN document_versions dv ON c.document_version_id = dv.id
                JOIN documents d ON dv.document_id = d.id
                WHERE c.embedding IS NOT NULL
                    AND c.id != cast(:clause_id as uuid)
                    AND 1 - (c.embedding <=> cast(:embedding as vector)) >= :min_similarity
                ORDER BY c.embedding <=> cast(:embedding as vector)
                LIMIT :limit
            """)
            result = await self.db.execute(
                sql,
                {
                    "embedding": embedding_str,
                    "clause_id": str(clause_id),
                    "min_similarity": min_similarity,
                    "limit": limit,
                },
            )

        rows = result.fetchall()

        return [
            SearchResult(
                clause_id=row.id,
                text=row.text,
                clause_type=row.clause_type,
                risk_level=row.risk_level,
                similarity=float(row.similarity),
                document_id=row.document_id,
                document_name=row.document_name,
            )
            for row in rows
        ]
