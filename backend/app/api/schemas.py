from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import UUID

from app.models.document import DocumentStatus
from app.models.clause import ClauseType, RiskLevel


# User schemas
class UserBase(BaseModel):
    email: str
    name: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Document schemas
class DocumentBase(BaseModel):
    original_filename: str
    file_type: str
    file_size: int


class DocumentCreate(DocumentBase):
    filename: str
    user_id: UUID


class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    status: str
    status_message: Optional[str] = None
    page_count: Optional[int] = None
    chunk_count: Optional[int] = None
    word_count: Optional[int] = None
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentProcessResponse(BaseModel):
    id: UUID
    status: str
    message: str


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int


class DocumentUploadResponse(BaseModel):
    id: UUID
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    status: str
    message: str


# Document Version schemas
class DocumentVersionResponse(BaseModel):
    id: UUID
    version_number: int
    storage_path: str
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Clause schemas
class ClauseResponse(BaseModel):
    id: UUID
    text: str
    clause_type: str
    risk_level: str
    risk_score: float
    risk_explanation: Optional[str] = None
    start_position: int
    end_position: int
    page_number: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Error schemas
class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
