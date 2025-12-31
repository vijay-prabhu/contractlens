-- Add processing-related columns to documents table
-- Run this in Supabase SQL Editor

-- Add extracted text column
ALTER TABLE documents ADD COLUMN IF NOT EXISTS extracted_text TEXT;

-- Add page count
ALTER TABLE documents ADD COLUMN IF NOT EXISTS page_count INTEGER;

-- Add chunk count for tracking how many chunks were created
ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunk_count INTEGER;

-- Add word count
ALTER TABLE documents ADD COLUMN IF NOT EXISTS word_count INTEGER;
