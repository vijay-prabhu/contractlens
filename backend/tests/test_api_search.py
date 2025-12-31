"""Tests for search API endpoints."""
import uuid
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient


class TestSearchClauses:
    """Tests for clause search endpoint."""

    def test_search_requires_auth(self):
        """Test that search endpoint requires authentication."""
        from app.main import app

        app.dependency_overrides.clear()

        with TestClient(app) as client:
            response = client.get("/api/v1/search?q=indemnification")

        assert response.status_code == 401

    def test_search_requires_minimum_query_length(self, client: TestClient):
        """Test that search requires minimum 3 character query."""
        response = client.get("/api/v1/search?q=ab")

        assert response.status_code == 422  # Validation error

    def test_search_returns_results(self, client: TestClient, mock_user):
        """Test that search returns results for valid query."""
        mock_result = MagicMock()
        mock_result.clause_id = uuid.uuid4()
        mock_result.text = "Sample indemnification clause"
        mock_result.clause_type = "indemnification"
        mock_result.risk_level = "high"
        mock_result.similarity = 0.85
        mock_result.document_id = uuid.uuid4()
        mock_result.document_name = "contract.pdf"

        with patch("app.api.search.SearchService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.search_clauses = AsyncMock(return_value=[mock_result])
            mock_service.return_value = mock_instance

            response = client.get("/api/v1/search?q=indemnification")

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "indemnification"
        assert data["total"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["clause_type"] == "indemnification"

    def test_search_filters_by_document(self, client: TestClient):
        """Test that search can filter by document_id."""
        doc_id = uuid.uuid4()

        with patch("app.api.search.SearchService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.search_clauses = AsyncMock(return_value=[])
            mock_service.return_value = mock_instance

            response = client.get(f"/api/v1/search?q=test&document_id={doc_id}")

        assert response.status_code == 200
        # Verify service was called with document_id
        mock_instance.search_clauses.assert_called_once()
        call_kwargs = mock_instance.search_clauses.call_args[1]
        assert call_kwargs["document_id"] == doc_id

    def test_search_respects_similarity_threshold(self, client: TestClient):
        """Test that search respects min_similarity parameter."""
        with patch("app.api.search.SearchService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.search_clauses = AsyncMock(return_value=[])
            mock_service.return_value = mock_instance

            response = client.get("/api/v1/search?q=test&min_similarity=0.8")

        assert response.status_code == 200
        call_kwargs = mock_instance.search_clauses.call_args[1]
        assert call_kwargs["min_similarity"] == 0.8

    def test_search_validates_similarity_range(self, client: TestClient):
        """Test that search validates similarity is between 0 and 1."""
        response = client.get("/api/v1/search?q=test&min_similarity=1.5")
        assert response.status_code == 422

        response = client.get("/api/v1/search?q=test&min_similarity=-0.1")
        assert response.status_code == 422


class TestSimilarClauses:
    """Tests for similar clauses endpoint."""

    def test_similar_requires_auth(self):
        """Test that similar clauses endpoint requires authentication."""
        from app.main import app

        app.dependency_overrides.clear()

        with TestClient(app) as client:
            response = client.get(f"/api/v1/search/similar/{uuid.uuid4()}")

        assert response.status_code == 401

    def test_similar_returns_results(self, client: TestClient, mock_user):
        """Test that similar clauses returns results."""
        source_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.clause_id = uuid.uuid4()
        mock_result.text = "Similar clause text"
        mock_result.clause_type = "termination"
        mock_result.risk_level = "medium"
        mock_result.similarity = 0.92
        mock_result.document_id = uuid.uuid4()
        mock_result.document_name = "other_contract.pdf"

        with patch("app.api.search.SearchService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.find_similar_clauses = AsyncMock(return_value=[mock_result])
            mock_service.return_value = mock_instance

            response = client.get(f"/api/v1/search/similar/{source_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["source_clause_id"] == str(source_id)
        assert data["total"] == 1
        assert len(data["similar_clauses"]) == 1

    def test_similar_validates_limit(self, client: TestClient):
        """Test that similar validates limit parameter range."""
        clause_id = uuid.uuid4()

        # Over max limit of 20
        response = client.get(f"/api/v1/search/similar/{clause_id}?limit=25")
        assert response.status_code == 422

        # Under min limit of 1
        response = client.get(f"/api/v1/search/similar/{clause_id}?limit=0")
        assert response.status_code == 422
