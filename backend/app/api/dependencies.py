"""FastAPI dependency injection factories for services."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.document_service import DocumentService
from app.services.search_service import SearchService
from app.services.comparison_service import ComparisonService


def get_document_service(
    db: AsyncSession = Depends(get_db),
) -> DocumentService:
    return DocumentService(db)


def get_search_service(
    db: AsyncSession = Depends(get_db),
) -> SearchService:
    return SearchService(db)


def get_comparison_service(
    db: AsyncSession = Depends(get_db),
) -> ComparisonService:
    return ComparisonService(db)
