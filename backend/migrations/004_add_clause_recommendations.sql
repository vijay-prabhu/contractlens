-- Migration: Add recommendations column to clauses table
-- Description: Store AI-generated recommendations for contract clauses

-- Add recommendations column (stores JSON array as text)
ALTER TABLE clauses ADD COLUMN IF NOT EXISTS recommendations TEXT;

-- Comment for documentation
COMMENT ON COLUMN clauses.recommendations IS 'JSON array of AI-generated recommendations for addressing clause risks';
