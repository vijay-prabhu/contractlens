"""Tests for document API endpoints."""
import uuid
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.models.document import Document, DocumentStatus
from app.models.user import User


class TestDocumentUpload:
    """Tests for document upload endpoint."""

    def test_upload_requires_auth(self):
        """Test that upload endpoint requires authentication."""
        from app.main import app
        from app.core.auth import get_current_user

        # Clear any mocks
        app.dependency_overrides.clear()

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/documents/upload",
                files={"file": ("test.pdf", b"content", "application/pdf")},
            )

        assert response.status_code == 401
        assert "Missing authentication token" in response.json()["detail"]

    def test_upload_rejects_invalid_file_type(self, client: TestClient):
        """Test that upload rejects non-PDF/DOCX files."""
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.txt", b"content", "text/plain")},
        )

        assert response.status_code == 400
        assert "File type not allowed" in response.json()["detail"]

    def test_upload_rejects_large_file(self, client: TestClient):
        """Test that upload rejects files over 10MB."""
        # Create content larger than 10MB
        large_content = b"x" * (11 * 1024 * 1024)

        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", large_content, "application/pdf")},
        )

        assert response.status_code == 400
        assert "File too large" in response.json()["detail"]


class TestDocumentList:
    """Tests for document list endpoint."""

    def test_list_requires_auth(self):
        """Test that list endpoint requires authentication."""
        from app.main import app

        app.dependency_overrides.clear()

        with TestClient(app) as client:
            response = client.get("/api/v1/documents")

        assert response.status_code == 401

    def test_list_returns_empty_for_new_user(self, client: TestClient):
        """Test that list returns empty for user with no documents."""
        with patch("app.api.documents.DocumentService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.get_documents = AsyncMock(return_value=[])
            mock_service.return_value = mock_instance

            response = client.get("/api/v1/documents")

        assert response.status_code == 200
        data = response.json()
        assert data["documents"] == []
        assert data["total"] == 0


class TestDocumentGet:
    """Tests for get document endpoint."""

    def test_get_requires_auth(self):
        """Test that get endpoint requires authentication."""
        from app.main import app

        app.dependency_overrides.clear()

        with TestClient(app) as client:
            response = client.get(f"/api/v1/documents/{uuid.uuid4()}")

        assert response.status_code == 401

    def test_get_returns_404_for_nonexistent(self, client: TestClient):
        """Test that get returns 404 for non-existent document."""
        with patch("app.api.documents.DocumentService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.get_document = AsyncMock(return_value=None)
            mock_service.return_value = mock_instance

            response = client.get(f"/api/v1/documents/{uuid.uuid4()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Document not found"

    def test_get_returns_403_for_other_user_document(
        self, client: TestClient, mock_user
    ):
        """Test that get returns 403 when accessing another user's document."""
        other_user_id = uuid.uuid4()

        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.user_id = other_user_id  # Different from mock_user.id
        mock_doc.filename = "test.pdf"

        with patch("app.api.documents.DocumentService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.get_document = AsyncMock(return_value=mock_doc)
            mock_service.return_value = mock_instance

            response = client.get(f"/api/v1/documents/{mock_doc.id}")

        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied"


class TestDocumentDelete:
    """Tests for delete document endpoint."""

    def test_delete_requires_auth(self):
        """Test that delete endpoint requires authentication."""
        from app.main import app

        app.dependency_overrides.clear()

        with TestClient(app) as client:
            response = client.delete(f"/api/v1/documents/{uuid.uuid4()}")

        assert response.status_code == 401

    def test_delete_returns_404_for_nonexistent(self, client: TestClient):
        """Test that delete returns 404 for non-existent document."""
        with patch("app.api.documents.DocumentService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.get_document = AsyncMock(return_value=None)
            mock_service.return_value = mock_instance

            response = client.delete(f"/api/v1/documents/{uuid.uuid4()}")

        assert response.status_code == 404

    def test_delete_returns_403_for_other_user_document(
        self, client: TestClient, mock_user
    ):
        """Test that delete returns 403 when deleting another user's document."""
        other_user_id = uuid.uuid4()

        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.user_id = other_user_id

        with patch("app.api.documents.DocumentService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.get_document = AsyncMock(return_value=mock_doc)
            mock_service.return_value = mock_instance

            response = client.delete(f"/api/v1/documents/{mock_doc.id}")

        assert response.status_code == 403


class TestDocumentAnalysis:
    """Tests for document analysis endpoint."""

    def test_analysis_requires_auth(self):
        """Test that analysis endpoint requires authentication."""
        from app.main import app

        app.dependency_overrides.clear()

        with TestClient(app) as client:
            response = client.get(f"/api/v1/documents/{uuid.uuid4()}/analysis")

        assert response.status_code == 401

    def test_analysis_returns_400_for_unprocessed_document(
        self, client: TestClient, mock_user
    ):
        """Test that analysis returns 400 for unprocessed document."""
        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.user_id = mock_user.id
        mock_doc.status = "uploaded"  # Not completed

        with patch("app.api.documents.DocumentService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.get_document = AsyncMock(return_value=mock_doc)
            mock_service.return_value = mock_instance

            response = client.get(f"/api/v1/documents/{mock_doc.id}/analysis")

        assert response.status_code == 400
        assert "not processed" in response.json()["detail"]


class TestVersionEndpoints:
    """Tests for version management endpoints."""

    def test_list_versions_requires_auth(self):
        """Test that list versions requires authentication."""
        from app.main import app

        app.dependency_overrides.clear()

        with TestClient(app) as client:
            response = client.get(f"/api/v1/documents/{uuid.uuid4()}/versions")

        assert response.status_code == 401

    def test_upload_version_requires_auth(self):
        """Test that upload version requires authentication."""
        from app.main import app

        app.dependency_overrides.clear()

        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/documents/{uuid.uuid4()}/versions",
                files={"file": ("test.pdf", b"content", "application/pdf")},
            )

        assert response.status_code == 401

    def test_upload_version_rejects_different_file_type(
        self, client: TestClient, mock_user
    ):
        """Test that upload version rejects different file type than original."""
        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.user_id = mock_user.id
        mock_doc.file_type = "pdf"

        with patch("app.api.documents.DocumentService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.get_document = AsyncMock(return_value=mock_doc)
            mock_instance.validate_file = MagicMock(return_value=(True, ""))
            mock_instance.get_file_type = MagicMock(return_value="docx")
            mock_service.return_value = mock_instance

            response = client.post(
                f"/api/v1/documents/{mock_doc.id}/versions",
                files={"file": ("test.docx", b"content", "application/vnd.openxmlformats")},
            )

        assert response.status_code == 400
        assert "must match original" in response.json()["detail"]
