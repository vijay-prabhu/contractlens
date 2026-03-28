"""Version comparison API endpoints."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, CurrentUser
from app.api.dependencies import get_comparison_service
from app.api.schemas import (
    ComparisonResponse,
    ClauseChangeResponse,
    TextDiffResponse,
    RiskSummaryResponse,
    ErrorResponse,
)
from app.services.comparison_service import ComparisonService
from app.models.document_version import DocumentVersion
from app.models.document import Document

router = APIRouter(prefix="/compare", tags=["comparison"])


@router.get(
    "",
    response_model=ComparisonResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid version IDs"},
        404: {"model": ErrorResponse, "description": "Version not found"},
    },
)
async def compare_versions(
    version1: UUID,
    version2: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: ComparisonService = Depends(get_comparison_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Compare two document versions.

    - **version1**: UUID of the first (older) version
    - **version2**: UUID of the second (newer) version

    Returns detailed comparison including:
    - Text-level diff (additions/deletions)
    - Clause-level changes (added, removed, modified, unchanged)
    - Semantic similarity scores for modified clauses
    - Risk change summary

    Requires authentication. Users can only compare versions of their own documents.
    """
    if version1 == version2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot compare a version with itself",
        )

    # Verify ownership of both versions
    for version_id in [version1, version2]:
        result = await db.execute(
            select(Document.user_id)
            .join(DocumentVersion, DocumentVersion.document_id == Document.id)
            .where(DocumentVersion.id == version_id)
        )
        owner_id = result.scalar_one_or_none()

        if not owner_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both versions not found",
            )

        if owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
    result = await service.compare_versions(version1, version2)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both versions not found",
        )

    # Convert to response model
    clause_changes = [
        ClauseChangeResponse(
            change_type=c.change_type.value,
            clause_type=c.clause_type,
            new_clause_id=c.new_clause_id,
            new_text=c.new_text,
            new_risk_level=c.new_risk_level,
            new_risk_score=c.new_risk_score,
            old_clause_id=c.old_clause_id,
            old_text=c.old_text,
            old_risk_level=c.old_risk_level,
            old_risk_score=c.old_risk_score,
            text_diff=c.text_diff,
            similarity_score=c.similarity_score,
            risk_change=c.risk_change,
        )
        for c in result.clause_changes
    ]

    return ComparisonResponse(
        version1_id=result.version1_id,
        version2_id=result.version2_id,
        version1_number=result.version1_number,
        version2_number=result.version2_number,
        clauses_added=result.clauses_added,
        clauses_removed=result.clauses_removed,
        clauses_modified=result.clauses_modified,
        clauses_unchanged=result.clauses_unchanged,
        text_diff=TextDiffResponse(
            additions=result.text_diff.additions,
            deletions=result.text_diff.deletions,
            diff_lines=result.text_diff.diff_lines,
        ),
        risk_summary=RiskSummaryResponse(
            old_overall_score=result.risk_summary.old_overall_score,
            new_overall_score=result.risk_summary.new_overall_score,
            risk_trend=result.risk_summary.risk_trend,
            critical_added=result.risk_summary.critical_added,
            critical_removed=result.risk_summary.critical_removed,
            high_risk_added=result.risk_summary.high_risk_added,
            high_risk_removed=result.risk_summary.high_risk_removed,
        ),
        clause_changes=clause_changes,
    )
