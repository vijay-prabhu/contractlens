'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import {
  Search,
  FileText,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  Info,
  Loader2,
  X,
  Filter,
  ArrowRight,
} from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { SearchResult, Document } from '@/types'

const riskIcons: Record<string, typeof AlertTriangle> = {
  critical: AlertTriangle,
  high: AlertCircle,
  medium: Info,
  low: CheckCircle,
}

const riskBadgeStyles: Record<string, string> = {
  critical: 'bg-red-100 text-red-700 border border-red-300',
  high: 'bg-orange-100 text-orange-700 border border-orange-300',
  medium: 'bg-yellow-100 text-yellow-700 border border-yellow-300',
  low: 'bg-green-100 text-green-700 border border-green-300',
}

const riskBorderStyles: Record<string, string> = {
  critical: 'border-l-4 border-l-red-500',
  high: 'border-l-4 border-l-orange-500',
  medium: 'border-l-4 border-l-yellow-500',
  low: 'border-l-4 border-l-green-500',
}

const clauseTypeLabels: Record<string, string> = {
  indemnification: 'Indemnification',
  limitation_of_liability: 'Limitation of Liability',
  termination: 'Termination',
  confidentiality: 'Confidentiality',
  payment_terms: 'Payment Terms',
  intellectual_property: 'Intellectual Property',
  governing_law: 'Governing Law',
  force_majeure: 'Force Majeure',
  warranty: 'Warranty',
  dispute_resolution: 'Dispute Resolution',
  assignment: 'Assignment',
  notice: 'Notice',
  amendment: 'Amendment',
  entire_agreement: 'Entire Agreement',
  other: 'Other',
}

function SimilarityBadge({ similarity }: { similarity: number }) {
  const percentage = Math.round(similarity * 100)
  const color =
    percentage >= 80
      ? 'text-green-600 bg-green-50'
      : percentage >= 60
      ? 'text-blue-600 bg-blue-50'
      : 'text-gray-600 bg-gray-50'

  return (
    <span className={cn('text-xs font-medium px-2 py-0.5 rounded', color)}>
      {percentage}% match
    </span>
  )
}

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasSearched, setHasSearched] = useState(false)
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>('')
  const [showFilters, setShowFilters] = useState(false)

  // Load documents for filter dropdown
  useEffect(() => {
    const loadDocuments = async () => {
      try {
        const response = await api.documents.list()
        setDocuments(response.documents.filter((d) => d.status === 'completed'))
      } catch {
        // Silently fail - documents filter is optional
      }
    }
    loadDocuments()
  }, [])

  const performSearch = useCallback(async () => {
    if (!query.trim()) return

    setLoading(true)
    setError(null)
    setHasSearched(true)

    try {
      const response = await api.search.clauses(query, {
        limit: 20,
        minSimilarity: 0.5,
        documentId: selectedDocumentId || undefined,
      })
      setResults(response.results)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed')
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [query, selectedDocumentId])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    performSearch()
  }

  const handleClear = () => {
    setQuery('')
    setResults([])
    setHasSearched(false)
    setError(null)
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Semantic Search</h1>
        <p className="mt-1 text-gray-600">
          Search across all your contracts using natural language. Find similar clauses and related content instantly.
        </p>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSubmit} className="mb-6">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for clauses... e.g., 'limitation of liability' or 'indemnification obligations'"
              className="w-full pl-12 pr-10 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 placeholder-gray-500"
            />
            {query && (
              <button
                type="button"
                onClick={handleClear}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            )}
          </div>

          <button
            type="button"
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              'px-4 py-3 border rounded-lg flex items-center gap-2 transition-colors',
              showFilters || selectedDocumentId
                ? 'border-blue-500 bg-blue-50 text-blue-700'
                : 'border-gray-300 text-gray-700 hover:bg-gray-50'
            )}
          >
            <Filter className="h-5 w-5" />
            <span className="hidden sm:inline">Filters</span>
          </button>

          <button
            type="submit"
            disabled={!query.trim() || loading}
            className="px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Search className="h-5 w-5" />
            )}
            <span className="hidden sm:inline">Search</span>
          </button>
        </div>

        {/* Filters Panel */}
        {showFilters && (
          <div className="mt-3 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div className="flex items-center gap-4">
              <label className="text-sm font-medium text-gray-700">
                Filter by document:
              </label>
              <select
                value={selectedDocumentId}
                onChange={(e) => setSelectedDocumentId(e.target.value)}
                className="flex-1 max-w-md px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All documents</option>
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.original_filename}
                  </option>
                ))}
              </select>
              {selectedDocumentId && (
                <button
                  type="button"
                  onClick={() => setSelectedDocumentId('')}
                  className="text-sm text-blue-600 hover:text-blue-800"
                >
                  Clear filter
                </button>
              )}
            </div>
          </div>
        )}
      </form>

      {/* Search Tips - Show before first search */}
      {!hasSearched && !loading && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h3 className="font-medium text-blue-900 mb-3">Search Tips</h3>
          <ul className="space-y-2 text-sm text-blue-800">
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-0.5">•</span>
              Use natural language to describe what you&apos;re looking for
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-0.5">•</span>
              Try clause types like &quot;indemnification&quot;, &quot;termination&quot;, or &quot;confidentiality&quot;
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-0.5">•</span>
              Search for concepts like &quot;liability cap&quot; or &quot;dispute resolution process&quot;
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-0.5">•</span>
              Filter by specific document to narrow your results
            </li>
          </ul>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-12">
          <Loader2 className="h-8 w-8 text-blue-600 animate-spin mb-3" />
          <p className="text-gray-600">Searching across your documents...</p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <AlertCircle className="h-8 w-8 text-red-500 mx-auto mb-3" />
          <p className="text-red-700">{error}</p>
          <button
            onClick={performSearch}
            className="mt-3 text-sm text-red-600 hover:text-red-800 font-medium"
          >
            Try again
          </button>
        </div>
      )}

      {/* No Results */}
      {hasSearched && !loading && !error && results.length === 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
          <Search className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No results found</h3>
          <p className="text-gray-600 mb-4">
            No clauses matched your search for &quot;{query}&quot;
          </p>
          <p className="text-sm text-gray-500">
            Try different keywords or check your document filter
          </p>
        </div>
      )}

      {/* Results */}
      {!loading && !error && results.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              Found <span className="font-medium">{results.length}</span> matching clauses
            </p>
          </div>

          <div className="space-y-3">
            {results.map((result) => {
              const Icon = riskIcons[result.risk_level] || Info
              return (
                <div
                  key={result.clause_id}
                  className={cn(
                    'bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow',
                    riskBorderStyles[result.risk_level]
                  )}
                >
                  {/* Header */}
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <FileText className="h-4 w-4 flex-shrink-0" />
                        <Link
                          href={`/dashboard/documents/${result.document_id}`}
                          className="hover:text-blue-600 truncate max-w-[200px]"
                          title={result.document_name}
                        >
                          {result.document_name}
                        </Link>
                      </div>
                      <span className="text-gray-300">•</span>
                      <span className="text-sm font-medium text-gray-700">
                        {clauseTypeLabels[result.clause_type] || result.clause_type}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 flex-shrink-0">
                      <SimilarityBadge similarity={result.similarity} />
                      <div
                        className={cn(
                          'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold',
                          riskBadgeStyles[result.risk_level]
                        )}
                      >
                        <Icon className="h-3 w-3 mr-1" />
                        {result.risk_level.charAt(0).toUpperCase() + result.risk_level.slice(1)}
                      </div>
                    </div>
                  </div>

                  {/* Clause Text */}
                  <p className="text-sm text-gray-600 line-clamp-3 mb-3">
                    {result.text}
                  </p>

                  {/* View Document Link */}
                  <Link
                    href={`/dashboard/documents/${result.document_id}`}
                    className="inline-flex items-center text-sm text-blue-600 hover:text-blue-800 font-medium"
                  >
                    View in document
                    <ArrowRight className="h-4 w-4 ml-1" />
                  </Link>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
