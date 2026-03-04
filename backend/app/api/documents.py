from typing import List
from uuid import UUID
import sentry_sdk
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, CurrentUser
from app.api.schemas import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    DocumentProcessResponse,
    DocumentAnalysisResponse,
    DocumentRiskAnalysis,
    RiskDistribution,
    ClauseResponse,
    DocumentVersionResponse,
    VersionListResponse,
    VersionUploadResponse,
    ErrorResponse,
)
from app.services.document_service import DocumentService
from app.workers import processor

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file"},
        500: {"model": ErrorResponse, "description": "Upload failed"},
    },
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a contract document (PDF or DOCX).

    - **file**: The document file to upload (max 10MB)

    Returns the created document with initial status.
    Requires authentication.
    """
    service = DocumentService(db)

    # Validate file
    is_valid, error_message = service.validate_file(
        file.filename or "unknown",
        file.size or 0,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )

    # Read file content
    file_content = await file.read()
    file_size = len(file_content)

    # Get file type
    file_type = service.get_file_type(file.filename or "unknown")

    try:
        # Upload to storage
        storage_path = await service.upload_to_storage(
            file_content,
            file.filename or "unknown",
            file.content_type or "application/octet-stream",
        )

        # Create document record
        document = await service.create_document(
            filename=storage_path.split("/")[-1],
            original_filename=file.filename or "unknown",
            file_type=file_type,
            file_size=file_size,
            user_id=current_user.id,
            storage_path=storage_path,
        )

        return DocumentUploadResponse(
            id=document.id,
            filename=document.filename,
            original_filename=document.original_filename,
            file_type=document.file_type,
            file_size=document.file_size,
            status=document.status,
            message="Document uploaded successfully. Processing will begin shortly.",
        )

    except Exception as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}",
        )


@router.get(
    "",
    response_model=DocumentListResponse,
)
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all documents for the current user.

    - **skip**: Number of documents to skip (pagination)
    - **limit**: Maximum number of documents to return

    Requires authentication.
    """
    service = DocumentService(db)
    documents = await service.get_documents(current_user.id, skip, limit)

    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                original_filename=doc.original_filename,
                file_type=doc.file_type,
                file_size=doc.file_size,
                status=doc.status,
                status_message=doc.status_message,
                page_count=doc.page_count,
                chunk_count=doc.chunk_count,
                word_count=doc.word_count,
                user_id=doc.user_id,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
            )
            for doc in documents
        ],
        total=len(documents),
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    responses={404: {"model": ErrorResponse, "description": "Document not found"}},
)
async def get_document(
    document_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific document by ID.

    Requires authentication. Users can only access their own documents.
    """
    service = DocumentService(db)
    document = await service.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Ownership check
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        status_message=document.status_message,
        page_count=document.page_count,
        chunk_count=document.chunk_count,
        word_count=document.word_count,
        user_id=document.user_id,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get(
    "/{document_id}/analysis",
    response_model=DocumentAnalysisResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"},
        400: {"model": ErrorResponse, "description": "Document not processed"},
    },
)
async def get_document_analysis(
    document_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get risk analysis for a processed document.

    Returns the document, risk analysis summary, and all classified clauses.
    Requires authentication. Users can only access their own documents.
    """
    service = DocumentService(db)
    document = await service.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Ownership check
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    if document.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document not processed. Current status: {document.status}",
        )

    # Get clauses for this document
    clauses = await service.get_document_clauses(document_id)

    # Calculate risk analysis from clauses
    risk_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    total_risk_score = 0.0

    for clause in clauses:
        risk_counts[clause.risk_level] = risk_counts.get(clause.risk_level, 0) + 1
        total_risk_score += clause.risk_score

    avg_risk_score = total_risk_score / len(clauses) if clauses else 0.0

    # Determine overall risk level
    critical_count = risk_counts.get("critical", 0)
    high_count = risk_counts.get("high", 0)

    if critical_count >= 1:
        overall_level = "critical"
    elif high_count >= 3 or (high_count >= 1 and avg_risk_score > 0.6):
        overall_level = "high"
    elif avg_risk_score > 0.4:
        overall_level = "medium"
    else:
        overall_level = "low"

    # Build response
    doc_response = DocumentResponse(
        id=document.id,
        filename=document.filename,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        status_message=document.status_message,
        page_count=document.page_count,
        chunk_count=document.chunk_count,
        word_count=document.word_count,
        user_id=document.user_id,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )

    risk_analysis = DocumentRiskAnalysis(
        overall_risk_score=round(avg_risk_score, 3),
        overall_risk_level=overall_level,
        clause_count=len(clauses),
        risk_distribution=RiskDistribution(**risk_counts),
        high_risk_clauses=high_count,
        critical_clauses=critical_count,
    )

    clause_responses = [
        ClauseResponse(
            id=c.id,
            text=c.text,
            clause_type=c.clause_type,
            risk_level=c.risk_level,
            risk_score=c.risk_score,
            risk_explanation=c.risk_explanation,
            recommendations=c.recommendations,
            start_position=c.start_position,
            end_position=c.end_position,
            page_number=c.page_number,
            created_at=c.created_at,
        )
        for c in clauses
    ]

    return DocumentAnalysisResponse(
        document=doc_response,
        risk_analysis=risk_analysis,
        clauses=clause_responses,
    )


@router.post(
    "/{document_id}/process",
    response_model=DocumentProcessResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"},
        409: {"model": ErrorResponse, "description": "Document already processed"},
    },
)
async def process_document(
    document_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger processing for a document.

    The document will be extracted and chunked for analysis.
    Requires authentication. Users can only process their own documents.
    """
    service = DocumentService(db)
    document = await service.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Ownership check
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    if document.status in ["processing", "extracting", "analyzing"]:
        return DocumentProcessResponse(
            id=document.id,
            status=document.status,
            message="Document is already being processed",
        )

    # For reprocessing completed documents, delete existing clauses first
    if document.status == "completed":
        # Get latest version and delete its clauses
        versions = await service.get_document_versions(document_id)
        if versions:
            latest_version = versions[0]  # Already sorted by version_number desc
            # Delete existing clauses for this version
            from app.models.clause import Clause
            await db.execute(
                delete(Clause).where(Clause.document_version_id == latest_version.id)
            )
            await db.commit()

    # Trigger processing
    success = await processor.process_document(document_id)

    if success:
        return DocumentProcessResponse(
            id=document_id,
            status="completed",
            message="Document processed successfully",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Processing failed",
        )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse, "description": "Document not found"}},
)
async def delete_document(
    document_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a document and all its versions.

    Requires authentication. Users can only delete their own documents.
    """
    service = DocumentService(db)

    # Check ownership first
    document = await service.get_document(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    deleted = await service.delete_document(document_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )


# Version management endpoints


@router.get(
    "/{document_id}/versions",
    response_model=VersionListResponse,
    responses={404: {"model": ErrorResponse, "description": "Document not found"}},
)
async def list_versions(
    document_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all versions of a document.

    Returns versions ordered by version number (newest first).
    Requires authentication. Users can only access their own documents.
    """
    service = DocumentService(db)
    document = await service.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Ownership check
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    versions = await service.get_document_versions(document_id)

    return VersionListResponse(
        document_id=document_id,
        versions=[
            DocumentVersionResponse(
                id=v.id,
                version_number=v.version_number,
                storage_path=v.storage_path,
                page_count=v.page_count,
                word_count=v.word_count,
                created_at=v.created_at,
            )
            for v in versions
        ],
        total=len(versions),
    )


@router.post(
    "/{document_id}/versions",
    response_model=VersionUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Upload failed"},
    },
)
async def upload_new_version(
    document_id: UUID,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a new version of an existing document.

    - **file**: The new version file (must be same type as original)

    The new version will be processed automatically.
    Requires authentication. Users can only upload to their own documents.
    """
    service = DocumentService(db)

    # Get existing document
    document = await service.get_document(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Ownership check
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Validate file
    is_valid, error_message = service.validate_file(
        file.filename or "unknown",
        file.size or 0,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )

    # Check file type matches original
    file_type = service.get_file_type(file.filename or "unknown")
    if file_type != document.file_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type must match original ({document.file_type})",
        )

    # Read file content
    file_content = await file.read()

    try:
        # Upload to storage
        storage_path = await service.upload_to_storage(
            file_content,
            file.filename or "unknown",
            file.content_type or "application/octet-stream",
        )

        # Create new version
        version = await service.create_new_version(
            document_id=document_id,
            storage_path=storage_path,
        )

        return VersionUploadResponse(
            id=version.id,
            version_number=version.version_number,
            document_id=document_id,
            status="uploaded",
            message=f"Version {version.version_number} uploaded. Processing will begin shortly.",
        )

    except Exception as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload version: {str(e)}",
        )
