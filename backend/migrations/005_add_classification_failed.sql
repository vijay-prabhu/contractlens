-- Add classification_failed column to track clauses where LLM classification errored
-- These show as "Classification failed" in the UI instead of fake low-risk scores
ALTER TABLE clauses ADD COLUMN IF NOT EXISTS classification_failed BOOLEAN DEFAULT FALSE;
