"""Search API endpoints."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, CurrentUser
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


class SearchResultResponse(BaseModel):
    """Search result response schema."""
    clause_id: UUID
    text: str
    clause_type: str
    risk_level: str
    similarity: float
    document_id: UUID
    document_name: str


class SearchResponse(BaseModel):
    """Search response with results."""
    query: str
    results: List[SearchResultResponse]
    total: int


class SimilarClausesResponse(BaseModel):
    """Similar clauses response."""
    source_clause_id: UUID
    similar_clauses: List[SearchResultResponse]
    total: int


@router.get(
    "",
    response_model=SearchResponse,
)
async def search_clauses(
    q: str = Query(..., min_length=3, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    min_similarity: float = Query(0.3, ge=0.0, le=1.0, description="Minimum similarity score (0.3 recommended for semantic search)"),
    document_id: Optional[UUID] = Query(None, description="Filter by document ID"),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search for clauses semantically similar to the query.

    Uses OpenAI embeddings and pgvector for semantic similarity search.
    Only searches within the current user's documents.

    - **q**: Search query (minimum 3 characters)
    - **limit**: Maximum number of results (1-50)
    - **min_similarity**: Minimum similarity threshold (0.0-1.0)
    - **document_id**: Optional filter to search within a specific document

    Requires authentication.
    """
    service = SearchService(db)

    results = await service.search_clauses(
        query=q,
        limit=limit,
        min_similarity=min_similarity,
        document_id=document_id,
        user_id=current_user.id,
    )

    return SearchResponse(
        query=q,
        results=[
            SearchResultResponse(
                clause_id=r.clause_id,
                text=r.text,
                clause_type=r.clause_type,
                risk_level=r.risk_level,
                similarity=r.similarity,
                document_id=r.document_id,
                document_name=r.document_name,
            )
            for r in results
        ],
        total=len(results),
    )


@router.get(
    "/similar/{clause_id}",
    response_model=SimilarClausesResponse,
)
async def find_similar_clauses(
    clause_id: UUID,
    limit: int = Query(5, ge=1, le=20, description="Maximum results"),
    min_similarity: float = Query(0.7, ge=0.0, le=1.0, description="Minimum similarity score"),
    include_same_document: bool = Query(False, description="Include clauses from same document"),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Find clauses similar to a given clause.

    Useful for comparing clauses across different contracts.
    Only searches within the current user's documents.

    - **clause_id**: ID of the source clause
    - **limit**: Maximum number of similar clauses (1-20)
    - **min_similarity**: Minimum similarity threshold (0.0-1.0)
    - **include_same_document**: Whether to include clauses from the same document

    Requires authentication.
    """
    service = SearchService(db)

    results = await service.find_similar_clauses(
        clause_id=clause_id,
        limit=limit,
        min_similarity=min_similarity,
        exclude_same_document=not include_same_document,
        user_id=current_user.id,
    )

    return SimilarClausesResponse(
        source_clause_id=clause_id,
        similar_clauses=[
            SearchResultResponse(
                clause_id=r.clause_id,
                text=r.text,
                clause_type=r.clause_type,
                risk_level=r.risk_level,
                similarity=r.similarity,
                document_id=r.document_id,
                document_name=r.document_name,
            )
            for r in results
        ],
        total=len(results),
    )
