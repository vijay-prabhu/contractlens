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
    """Types of contract clauses — generated from config/clause_types.yaml."""

    # Financial risk
    INDEMNIFICATION = "indemnification"
    LIMITATION_OF_LIABILITY = "limitation_of_liability"
    PAYMENT_TERMS = "payment_terms"
    INSURANCE = "insurance"

    # Operational risk
    TERMINATION = "termination"
    FORCE_MAJEURE = "force_majeure"
    SERVICE_LEVELS = "service_levels"
    CHANGE_OF_CONTROL = "change_of_control"

    # IP and data
    INTELLECTUAL_PROPERTY = "intellectual_property"
    CONFIDENTIALITY = "confidentiality"
    DATA_PROTECTION = "data_protection"

    # Restrictive covenants
    NON_COMPETE = "non_compete"
    EXCLUSIVITY = "exclusivity"

    # Compliance and governance
    WARRANTY = "warranty"
    DISPUTE_RESOLUTION = "dispute_resolution"
    AUDIT_RIGHTS = "audit_rights"
    GOVERNING_LAW = "governing_law"
    REPRESENTATIONS = "representations"

    # Administrative
    ASSIGNMENT = "assignment"
    NOTICE = "notice"
    AMENDMENT = "amendment"
    ENTIRE_AGREEMENT = "entire_agreement"

    # Catch-all
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
    classification_failed: Mapped[bool] = mapped_column(default=False)

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
