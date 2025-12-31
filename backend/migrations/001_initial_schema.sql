-- ContractLens Initial Schema
-- Run this in Supabase SQL Editor

-- Enable pgvector extension (should already be enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Create index on email
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'processing', 'extracting', 'analyzing', 'completed', 'failed')),
    status_message TEXT,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Create index on user_id
CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents(user_id);

-- Document versions table
CREATE TABLE IF NOT EXISTS document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_number INTEGER DEFAULT 1,
    storage_path VARCHAR(500) NOT NULL,
    extracted_text TEXT,
    page_count INTEGER,
    word_count INTEGER,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Create index on document_id
CREATE INDEX IF NOT EXISTS ix_document_versions_document_id ON document_versions(document_id);

-- Clauses table
CREATE TABLE IF NOT EXISTS clauses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text TEXT NOT NULL,
    clause_type VARCHAR(50) DEFAULT 'other' CHECK (clause_type IN (
        'indemnification', 'limitation_of_liability', 'termination', 'confidentiality',
        'payment_terms', 'intellectual_property', 'governing_law', 'force_majeure',
        'warranty', 'dispute_resolution', 'assignment', 'notice', 'amendment',
        'entire_agreement', 'other'
    )),
    risk_level VARCHAR(20) DEFAULT 'low' CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    risk_score FLOAT DEFAULT 0.0,
    risk_explanation TEXT,
    start_position INTEGER NOT NULL,
    end_position INTEGER NOT NULL,
    page_number INTEGER,
    embedding vector(1536),  -- OpenAI ada-002 embedding dimensions
    document_version_id UUID NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Create index on document_version_id
CREATE INDEX IF NOT EXISTS ix_clauses_document_version_id ON clauses(document_version_id);

-- Create vector similarity search index for embeddings
CREATE INDEX IF NOT EXISTS ix_clauses_embedding ON clauses USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Create a default test user for development
INSERT INTO users (email, name)
VALUES ('test@contractlens.dev', 'Test User')
ON CONFLICT (email) DO NOTHING;

-- Grant permissions (if using Row Level Security)
-- ALTER TABLE users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE clauses ENABLE ROW LEVEL SECURITY;
