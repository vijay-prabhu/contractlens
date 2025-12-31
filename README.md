# ContractLens

AI-powered contract review and risk analysis tool.

## Overview

ContractLens helps legal teams and businesses analyze contracts quickly by:
- Extracting and parsing PDF/DOCX documents
- Identifying key clauses using AI
- Scoring risk levels
- Comparing document versions with semantic diff

## Tech Stack

### Backend
- **Framework:** FastAPI (Python)
- **Database:** PostgreSQL + pgvector (Supabase)
- **Cache/Queue:** Redis
- **AI:** OpenAI API (embeddings + GPT-4)

### Frontend
- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS

### Infrastructure
- **Deployment:** Railway/Render (backend), Vercel (frontend)
- **Storage:** Supabase Storage

## Project Structure

```
contractlens/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── services/
│   │   └── workers/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   └── types/
│   ├── package.json
│   └── Dockerfile
├── docs/
│   ├── architecture.md
│   ├── adr/
│   └── api-spec.yaml
├── docker-compose.yml
└── README.md
```

## Getting Started

Documentation coming soon.

## License

Private - All rights reserved.
