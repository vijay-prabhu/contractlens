# Contributing to ContractLens

Thanks for your interest in contributing. This guide covers the setup, conventions, and process.

## Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Poetry (Python package manager)
- A Supabase account (free tier works)
- An OpenAI API key

### Getting Started

1. Fork and clone the repo
2. Configure environment variables:
   ```bash
   cp .env.example .env             # Backend — add your Supabase + OpenAI keys
   cp frontend/.env.example frontend/.env.local  # Frontend — add Supabase public keys
   ```
3. Install dependencies:
   ```bash
   cd backend && poetry install
   cd ../frontend && npm install
   ```
4. Set up the database:
   - Run SQL files from `backend/migrations/` in the Supabase SQL editor
   - Enable the `vector` extension
5. Start the app:
   ```bash
   ./dev-start.sh
   ```
   Backend runs on http://localhost:8200, frontend on http://localhost:3200.

## Project Structure

```
backend/app/
  api/              Route handlers (thin — delegate to services)
  api/dependencies.py   Service injection factories
  core/             Config, auth, database, constants
  models/           SQLAlchemy models
  services/         Business logic
  workers/          Background processing

frontend/src/
  app/              Next.js pages (App Router)
  components/       React components
  lib/              API client, utilities, constants
  types/            TypeScript definitions

docs/adr/           Architecture Decision Records
```

## Code Style

### Python (Backend)

- **Formatter**: Black (line-length 100)
- **Linter**: Ruff
- **Types**: Mypy (strict)
- Run all checks: `cd backend && poetry run ruff check . && poetry run black --check . && poetry run mypy .`

Key rules:
- Use `Depends()` for service injection, not manual instantiation
- Business logic in `services/`, not in route handlers
- Magic numbers go in `core/constants.py`
- Use `datetime.now(timezone.utc)`, not `datetime.utcnow()`
- Imports at the top of files

### TypeScript (Frontend)

- **Linter**: ESLint with Next.js + TypeScript rules
- **Formatter**: Prettier
- **Strict mode**: Enabled — no `any` types
- Run checks: `cd frontend && npm run lint`

Key rules:
- Intervals and timeouts in `lib/constants.ts`
- Auth logic uses shared helpers in `lib/api.ts`
- Error boundaries at every route level (`error.tsx`)
- `'use client'` only where needed

## Architecture Decisions

Before making structural changes, check `docs/adr/` for existing decisions. If your change introduces a new pattern, technology, or significant trade-off, write an ADR.

## Pull Request Process

1. Create a branch from `main`
2. Make focused changes — one concern per PR
3. Run tests: `cd backend && poetry run pytest -v`
4. Run linters for both backend and frontend
5. Write a clear PR description — what changed and why
6. Link related issues if applicable

## Commit Messages

Use descriptive commit messages. Format:

```
<type>: <short description>

<optional longer explanation>
```

Types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `perf`

## Reporting Issues

Open an issue with:
- What you expected
- What happened instead
- Steps to reproduce
- Screenshots if applicable
