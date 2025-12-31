import uuid
from datetime import datetime
from typing import Optional, List, BinaryIO
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.models.document import Document, DocumentStatus
from app.models.document_version import DocumentVersion
from app.models.clause import Clause
from app.models.user import User
from app.core.supabase import get_supabase_client

# Allowed file types
ALLOWED_EXTENSIONS = {"pdf", "docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class DocumentService:
    """Service for document operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.supabase = get_supabase_client()

    @staticmethod
    def validate_file(filename: str, file_size: int) -> tuple[bool, str]:
        """Validate file type and size."""
        # Check extension
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"

        # Check size
        if file_size > MAX_FILE_SIZE:
            return False, f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB"

        return True, ""

    @staticmethod
    def get_file_type(filename: str) -> str:
        """Get file type from filename."""
        return filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"

    async def get_or_create_test_user(self) -> User:
        """Get or create a test user for development."""
        result = await self.db.execute(
            select(User).where(User.email == "test@contractlens.dev")
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                email="test@contractlens.dev",
                name="Test User",
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

        return user

    async def upload_to_storage(
        self, file_content: bytes, filename: str, content_type: str
    ) -> str:
        """Upload file to Supabase Storage."""
        # Generate unique path
        unique_filename = f"{uuid.uuid4()}_{filename}"
        storage_path = f"uploads/{unique_filename}"

        # Upload to Supabase Storage
        self.supabase.storage.from_("documents").upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": content_type},
        )

        return storage_path

    async def create_document(
        self,
        filename: str,
        original_filename: str,
        file_type: str,
        file_size: int,
        user_id: uuid.UUID,
        storage_path: str,
    ) -> Document:
        """Create a new document record."""
        # Create document
        document = Document(
            filename=filename,
            original_filename=original_filename,
            file_type=file_type,
            file_size=file_size,
            user_id=user_id,
            status=DocumentStatus.UPLOADED.value,
        )
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        # Create initial version
        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            storage_path=storage_path,
        )
        self.db.add(version)
        await self.db.commit()

        return document

    async def get_document(self, document_id: uuid.UUID) -> Optional[Document]:
        """Get a document by ID."""
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.versions))
            .where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_documents(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> List[Document]:
        """Get all documents for a user."""
        result = await self.db.execute(
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        document_id: uuid.UUID,
        status: DocumentStatus,
        message: Optional[str] = None,
    ) -> None:
        """Update document status."""
        await self.db.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(
                status=status,
                status_message=message,
                updated_at=datetime.utcnow(),
            )
        )
        await self.db.commit()

    async def delete_document(self, document_id: uuid.UUID) -> bool:
        """Delete a document and its storage file."""
        document = await self.get_document(document_id)
        if not document:
            return False

        # Delete from storage
        for version in document.versions:
            try:
                self.supabase.storage.from_("documents").remove([version.storage_path])
            except Exception:
                pass  # Ignore storage errors

        # Delete from database (cascade will handle versions and clauses)
        await self.db.delete(document)
        await self.db.commit()

        return True

    async def get_document_clauses(
        self, document_id: uuid.UUID
    ) -> List[Clause]:
        """Get all clauses for a document.

        Args:
            document_id: UUID of the document

        Returns:
            List of clauses ordered by position
        """
        # First get the document version(s)
        result = await self.db.execute(
            select(DocumentVersion.id)
            .where(DocumentVersion.document_id == document_id)
        )
        version_ids = [row[0] for row in result.fetchall()]

        if not version_ids:
            return []

        # Get clauses for those versions, ordered by risk score (highest first)
        result = await self.db.execute(
            select(Clause)
            .where(Clause.document_version_id.in_(version_ids))
            .order_by(Clause.risk_score.desc(), Clause.start_position)
        )

        return list(result.scalars().all())

    async def get_document_versions(
        self, document_id: uuid.UUID
    ) -> List[DocumentVersion]:
        """Get all versions of a document.

        Args:
            document_id: UUID of the document

        Returns:
            List of versions ordered by version number (newest first)
        """
        result = await self.db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
        )
        return list(result.scalars().all())

    async def create_new_version(
        self,
        document_id: uuid.UUID,
        storage_path: str,
    ) -> DocumentVersion:
        """Create a new version of a document.

        Args:
            document_id: UUID of the parent document
            storage_path: Path in Supabase storage

        Returns:
            The created DocumentVersion
        """
        # Get current highest version number
        result = await self.db.execute(
            select(DocumentVersion.version_number)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
        current_version = result.scalar_one_or_none() or 0

        # Create new version
        version = DocumentVersion(
            document_id=document_id,
            version_number=current_version + 1,
            storage_path=storage_path,
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(version)

        # Update document status to trigger reprocessing
        await self.db.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(
                status=DocumentStatus.UPLOADED.value,
                status_message=f"Version {version.version_number} uploaded, pending processing",
            )
        )
        await self.db.commit()

        return version
