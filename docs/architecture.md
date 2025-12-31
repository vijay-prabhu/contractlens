# ContractLens Architecture

## Overview

ContractLens is an AI-powered contract review and risk analysis tool that helps legal teams analyze contracts quickly and efficiently.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                        │
│  - Document upload                                               │
│  - Review dashboard                                              │
│  - Version diff viewer                                           │
│  - Risk highlighting                                             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway (FastAPI)                       │
│  - JWT Authentication                                            │
│  - File upload handling                                          │
│  - Background job orchestration                                  │
│  - WebSocket for progress updates                                │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
        ┌──────────┐    ┌──────────────┐    ┌──────────┐
        │  Redis   │    │  PostgreSQL  │    │  Object  │
        │  Queue   │    │  + pgvector  │    │  Storage │
        └──────────┘    └──────────────┘    └──────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Processing Pipeline                           │
│  1. Document parsing (PyMuPDF / python-docx)                     │
│  2. Text chunking (LangChain)                                    │
│  3. Embedding generation (OpenAI)                                │
│  4. Clause classification (GPT-4)                                │
│  5. Risk scoring (GPT-4 + rules)                                 │
│  6. Version diff (custom + semantic)                             │
└─────────────────────────────────────────────────────────────────┘
```

## Technology Stack

### Backend
- **Framework:** FastAPI (Python 3.11)
- **Database:** PostgreSQL + pgvector (hosted on Supabase)
- **Cache/Queue:** Redis
- **AI:** OpenAI API (embeddings + GPT-4o-mini)

### Frontend
- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS

### Infrastructure
- **Database Hosting:** Supabase (free tier)
- **Backend Deployment:** Railway / Render
- **Frontend Deployment:** Vercel
- **Object Storage:** Supabase Storage

## Data Flow

1. User uploads a contract (PDF/DOCX)
2. Backend stores file in Supabase Storage
3. Background worker extracts text
4. Text is chunked and embedded via OpenAI
5. Embeddings stored in pgvector
6. GPT-4o-mini classifies clauses and scores risk
7. Results displayed in frontend dashboard

## Security Considerations

- All API keys stored in environment variables
- Row Level Security (RLS) on Supabase tables
- CORS configured for frontend origin only
- File upload validation and size limits
