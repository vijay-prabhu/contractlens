from datetime import datetime
from enum import Enum
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Text, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
import uuid

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.document_version import DocumentVersion


class ClauseType(str, Enum):
    """Types of contract clauses."""

    INDEMNIFICATION = "indemnification"
    LIMITATION_OF_LIABILITY = "limitation_of_liability"
    TERMINATION = "termination"
    CONFIDENTIALITY = "confidentiality"
    PAYMENT_TERMS = "payment_terms"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    GOVERNING_LAW = "governing_law"
    FORCE_MAJEURE = "force_majeure"
    WARRANTY = "warranty"
    DISPUTE_RESOLUTION = "dispute_resolution"
    ASSIGNMENT = "assignment"
    NOTICE = "notice"
    AMENDMENT = "amendment"
    ENTIRE_AGREEMENT = "entire_agreement"
    OTHER = "other"


class RiskLevel(str, Enum):
    """Risk level for clauses."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Clause(Base, TimestampMixin):
    """Clause model representing an identified clause in a document."""

    __tablename__ = "clauses"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    text: Mapped[str] = mapped_column(Text)
    clause_type: Mapped[str] = mapped_column(
        String(50),
        default=ClauseType.OTHER.value,
    )
    risk_level: Mapped[str] = mapped_column(
        String(20),
        default=RiskLevel.LOW.value,
    )
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 to 1.0
    risk_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of recommendations

    # Position in document
    start_position: Mapped[int] = mapped_column(Integer)
    end_position: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Embedding for semantic search (1536 dimensions for OpenAI ada-002)
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(1536), nullable=True
    )

    # Foreign keys
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        index=True,
    )

    # Relationships
    document_version: Mapped["DocumentVersion"] = relationship(
        "DocumentVersion", back_populates="clauses"
    )

    def __repr__(self) -> str:
        return f"<Clause {self.clause_type} ({self.risk_level})>"
