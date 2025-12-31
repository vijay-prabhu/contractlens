from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.clause import Clause


class DocumentVersion(Base, TimestampMixin):
    """Document version model for tracking different versions of a contract."""

    __tablename__ = "document_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    storage_path: Mapped[str] = mapped_column(String(500))  # Supabase storage path
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Foreign keys
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="versions")
    clauses: Mapped[List["Clause"]] = relationship(
        "Clause", back_populates="document_version", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DocumentVersion {self.document_id} v{self.version_number}>"
