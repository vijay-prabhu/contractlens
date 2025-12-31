# ADR-001: Technology Stack Selection

## Status
Accepted

## Date
2024-12-30

## Context
We need to select a technology stack for ContractLens, an AI-powered contract review tool. The stack must support:
- Document upload and processing (PDF/DOCX)
- AI/ML capabilities for clause classification and risk analysis
- Vector similarity search for semantic comparison
- Real-time updates during processing
- Rapid development for a 2-week sprint

## Decision

### Backend: FastAPI (Python)
**Rationale:**
- Excellent async support for I/O-bound AI operations
- First-class OpenAPI documentation
- Strong Python ecosystem for document processing (PyMuPDF, python-docx)
- LangChain integration is Python-native
- Familiar to the team (Django background)

**Alternatives considered:**
- Node.js/Express: Better for real-time, but weaker document processing libraries
- Go: Fast, but AI/ML ecosystem is limited

### Database: PostgreSQL + pgvector (Supabase)
**Rationale:**
- pgvector extension provides native vector similarity search
- Supabase offers free tier with managed PostgreSQL
- Built-in authentication and storage solutions
- Reduces infrastructure complexity

**Alternatives considered:**
- Pinecone: Dedicated vector DB, but adds another service and cost
- Weaviate: More features, but overkill for MVP

### Frontend: Next.js 14 + TypeScript
**Rationale:**
- App Router provides modern React patterns
- Server components for better performance
- TypeScript for type safety
- Vercel deployment is seamless

**Alternatives considered:**
- Remix: Excellent, but smaller ecosystem
- SvelteKit: Learning curve for team

### AI: OpenAI API
**Rationale:**
- text-embedding-3-small is cost-effective (~$0.02/1M tokens)
- GPT-4o-mini provides excellent classification at low cost
- Well-documented, reliable API
- LangChain has first-class support

**Alternatives considered:**
- Anthropic Claude: Excellent quality, but embeddings require Voyage AI (additional service)
- Local models: Requires GPU, not feasible on M1 MacBook Air

## Consequences

### Positive
- Fast development with familiar technologies
- Low infrastructure cost (~$10-15 for project)
- Good documentation and community support
- Easy deployment to free tiers

### Negative
- Vendor lock-in to OpenAI for AI capabilities
- Supabase free tier has limitations (500MB database)
- Python backend may need optimization for high concurrency

### Risks
- OpenAI API rate limits during batch processing
- Supabase connection limits on free tier

## References
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Supabase pgvector Guide](https://supabase.com/docs/guides/ai/vector-columns)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
