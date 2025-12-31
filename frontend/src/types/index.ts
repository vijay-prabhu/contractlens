export interface User {
  id: string
  email: string
  name?: string
}

export interface Document {
  id: string
  filename: string
  original_filename: string
  file_type: string
  file_size: number
  status: DocumentStatus
  status_message?: string
  page_count?: number
  chunk_count?: number
  word_count?: number
  user_id: string
  created_at: string
  updated_at: string
}

export type DocumentStatus =
  | 'uploaded'
  | 'processing'
  | 'extracting'
  | 'analyzing'
  | 'completed'
  | 'failed'

export interface DocumentVersion {
  id: string
  version_number: number
  storage_path: string
  page_count?: number
  word_count?: number
  created_at: string
}

export interface Clause {
  id: string
  text: string
  clause_type: ClauseType
  risk_level: RiskLevel
  risk_score: number
  risk_explanation?: string
  recommendations?: string[]
  start_position: number
  end_position: number
  page_number?: number
  created_at: string
}

export type ClauseType =
  | 'indemnification'
  | 'limitation_of_liability'
  | 'termination'
  | 'confidentiality'
  | 'payment_terms'
  | 'intellectual_property'
  | 'governing_law'
  | 'force_majeure'
  | 'warranty'
  | 'dispute_resolution'
  | 'assignment'
  | 'notice'
  | 'amendment'
  | 'entire_agreement'
  | 'other'

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

export interface RiskDistribution {
  low: number
  medium: number
  high: number
  critical: number
}

export interface DocumentRiskAnalysis {
  overall_risk_score: number
  overall_risk_level: RiskLevel
  clause_count: number
  risk_distribution: RiskDistribution
  high_risk_clauses: number
  critical_clauses: number
}

export interface DocumentAnalysis {
  document: Document
  risk_analysis: DocumentRiskAnalysis
  clauses: Clause[]
}

export interface DocumentListResponse {
  documents: Document[]
  total: number
}

export interface VersionListResponse {
  document_id: string
  versions: DocumentVersion[]
  total: number
}

export interface ClauseChange {
  change_type: 'added' | 'removed' | 'modified' | 'unchanged'
  clause_type: string
  new_clause_id?: string
  new_text?: string
  new_risk_level?: string
  new_risk_score?: number
  old_clause_id?: string
  old_text?: string
  old_risk_level?: string
  old_risk_score?: number
  text_diff?: string
  similarity_score?: number
  risk_change?: 'increased' | 'decreased' | 'unchanged'
}

export interface TextDiff {
  additions: number
  deletions: number
  diff_lines: string[]
}

export interface RiskSummary {
  old_overall_score: number
  new_overall_score: number
  risk_trend: 'increased' | 'decreased' | 'unchanged'
  critical_added: number
  critical_removed: number
  high_risk_added: number
  high_risk_removed: number
}

export interface ComparisonResult {
  version1_id: string
  version2_id: string
  version1_number: number
  version2_number: number
  clauses_added: number
  clauses_removed: number
  clauses_modified: number
  clauses_unchanged: number
  text_diff: TextDiff
  risk_summary: RiskSummary
  clause_changes: ClauseChange[]
}

export interface SearchResult {
  clause_id: string
  text: string
  clause_type: string
  risk_level: string
  similarity: number
  document_id: string
  document_name: string
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
  total: number
}
