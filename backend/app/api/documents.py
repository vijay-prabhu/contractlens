from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.schemas import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    ErrorResponse,
)
from app.services.document_service import DocumentService

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
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a contract document (PDF or DOCX).

    - **file**: The document file to upload (max 10MB)

    Returns the created document with initial status.
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

    # Get or create test user (for development)
    user = await service.get_or_create_test_user()

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
            user_id=user.id,
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
    db: AsyncSession = Depends(get_db),
):
    """
    List all documents for the current user.

    - **skip**: Number of documents to skip (pagination)
    - **limit**: Maximum number of documents to return
    """
    service = DocumentService(db)

    # Get test user for development
    user = await service.get_or_create_test_user()

    documents = await service.get_documents(user.id, skip, limit)

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
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific document by ID.
    """
    service = DocumentService(db)
    document = await service.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        status_message=document.status_message,
        user_id=document.user_id,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse, "description": "Document not found"}},
)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a document and all its versions.
    """
    service = DocumentService(db)
    deleted = await service.delete_document(document_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
