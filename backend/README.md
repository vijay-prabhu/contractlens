# ContractLens Backend

FastAPI backend for AI-powered contract review and risk analysis.

## Setup

```bash
# Install dependencies
poetry install

# Run development server
poetry run uvicorn app.main:app --reload
```

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `POST /documents/upload` - Upload a document
- `GET /documents` - List all documents
- `GET /documents/{id}` - Get document details
