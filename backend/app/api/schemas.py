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


# Risk Analysis schemas
class RiskDistribution(BaseModel):
    low: int = 0
    medium: int = 0
    high: int = 0
    critical: int = 0


class DocumentRiskAnalysis(BaseModel):
    overall_risk_score: float = Field(..., ge=0.0, le=1.0)
    overall_risk_level: str
    clause_count: int
    risk_distribution: RiskDistribution
    high_risk_clauses: int
    critical_clauses: int


class DocumentAnalysisResponse(BaseModel):
    document: DocumentResponse
    risk_analysis: DocumentRiskAnalysis
    clauses: List[ClauseResponse]


class ClauseTypeCount(BaseModel):
    clause_type: str
    count: int
    avg_risk_score: float


class DocumentAnalysisSummary(BaseModel):
    document_id: UUID
    overall_risk_level: str
    overall_risk_score: float
    total_clauses: int
    clause_type_breakdown: List[ClauseTypeCount]
    top_risk_clauses: List[ClauseResponse]


# Version Comparison schemas
class ClauseChangeResponse(BaseModel):
    change_type: str  # added, removed, modified, unchanged
    clause_type: str

    # New clause info (for added/modified/unchanged)
    new_clause_id: Optional[UUID] = None
    new_text: Optional[str] = None
    new_risk_level: Optional[str] = None
    new_risk_score: Optional[float] = None

    # Old clause info (for removed/modified/unchanged)
    old_clause_id: Optional[UUID] = None
    old_text: Optional[str] = None
    old_risk_level: Optional[str] = None
    old_risk_score: Optional[float] = None

    # Diff info (for modified)
    text_diff: Optional[str] = None
    similarity_score: Optional[float] = None
    risk_change: Optional[str] = None  # increased, decreased, unchanged


class TextDiffResponse(BaseModel):
    additions: int = 0
    deletions: int = 0
    diff_lines: List[str] = []


class RiskSummaryResponse(BaseModel):
    old_overall_score: float = 0.0
    new_overall_score: float = 0.0
    risk_trend: str = "unchanged"  # increased, decreased, unchanged
    critical_added: int = 0
    critical_removed: int = 0
    high_risk_added: int = 0
    high_risk_removed: int = 0


class ComparisonResponse(BaseModel):
    version1_id: UUID
    version2_id: UUID
    version1_number: int
    version2_number: int

    # Summary statistics
    clauses_added: int = 0
    clauses_removed: int = 0
    clauses_modified: int = 0
    clauses_unchanged: int = 0

    # Text diff summary
    text_diff: TextDiffResponse

    # Risk comparison
    risk_summary: RiskSummaryResponse

    # Detailed clause changes
    clause_changes: List[ClauseChangeResponse]


class VersionListResponse(BaseModel):
    document_id: UUID
    versions: List[DocumentVersionResponse]
    total: int


class VersionUploadResponse(BaseModel):
    id: UUID
    version_number: int
    document_id: UUID
    status: str
    message: str


# Error schemas
class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
