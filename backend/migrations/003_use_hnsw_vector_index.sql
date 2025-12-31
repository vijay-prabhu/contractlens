-- Switch from ivfflat to HNSW vector index
-- Run this in Supabase SQL Editor
--
-- Why: ivfflat requires sufficient training data to build clusters effectively.
-- With small datasets, it returns incorrect results when using ORDER BY.
-- HNSW (Hierarchical Navigable Small World) works consistently at any scale.

-- Drop the problematic ivfflat index
DROP INDEX IF EXISTS ix_clauses_embedding;

-- Create HNSW index for vector similarity search
-- Parameters:
--   m = 16: Max connections per layer (higher = better recall, more memory)
--   ef_construction = 64: Build-time search width (higher = better quality, slower build)
CREATE INDEX ix_clauses_embedding ON clauses
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
