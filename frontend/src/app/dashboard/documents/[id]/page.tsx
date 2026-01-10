'use client'

import { useEffect, useState, useRef } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft,
  FileText,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  Info,
  RefreshCw,
  Clock,
  FileCheck,
  Loader2,
  GitCompare,
  History,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Upload,
  HelpCircle,
} from 'lucide-react'
import { api } from '@/lib/api'
import { cn, formatDate, formatFileSize, getStatusColor } from '@/lib/utils'
import { useToast } from '@/components/toast'
import type { Document, DocumentAnalysis, DocumentVersion, RiskLevel } from '@/types'

const riskIcons: Record<RiskLevel, typeof AlertTriangle> = {
  critical: AlertTriangle,
  high: AlertCircle,
  medium: Info,
  low: CheckCircle,
}

const riskLabels: Record<RiskLevel, string> = {
  critical: 'Critical Risk',
  high: 'High Risk',
  medium: 'Medium Risk',
  low: 'Low Risk',
}

const riskCardStyles: Record<RiskLevel, string> = {
  critical: 'bg-red-100 border border-red-300',
  high: 'bg-orange-100 border border-orange-300',
  medium: 'bg-yellow-100 border border-yellow-300',
  low: 'bg-green-100 border border-green-300',
}

const riskBadgeStyles: Record<RiskLevel, string> = {
  critical: 'bg-red-100 text-red-700 border border-red-300',
  high: 'bg-orange-100 text-orange-700 border border-orange-300',
  medium: 'bg-yellow-100 text-yellow-700 border border-yellow-300',
  low: 'bg-green-100 text-green-700 border border-green-300',
}

const riskIconStyles: Record<RiskLevel, string> = {
  critical: 'text-red-600',
  high: 'text-orange-600',
  medium: 'text-yellow-600',
  low: 'text-green-600',
}

const riskBorderStyles: Record<RiskLevel, string> = {
  critical: 'border-l-4 border-l-red-500',
  high: 'border-l-4 border-l-orange-500',
  medium: 'border-l-4 border-l-yellow-500',
  low: 'border-l-4 border-l-green-500',
}

export default function DocumentDetailPage() {
  const params = useParams()
  const id = params.id as string
  const { showToast } = useToast()
  const [document, setDocument] = useState<Document | null>(null)
  const [analysis, setAnalysis] = useState<DocumentAnalysis | null>(null)
  const [versions, setVersions] = useState<DocumentVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reprocessing, setReprocessing] = useState(false)
  const [selectedVersions, setSelectedVersions] = useState<string[]>([])
  const [uploadingVersion, setUploadingVersion] = useState(false)
  const [showVersionHelp, setShowVersionHelp] = useState(false)
  const [expandedClauses, setExpandedClauses] = useState<Set<string>>(new Set())
  const [riskFilter, setRiskFilter] = useState<RiskLevel | 'all'>('all')
  const versionFileInputRef = useRef<HTMLInputElement>(null)

  const toggleClauseExpanded = (clauseId: string) => {
    setExpandedClauses((prev) => {
      const next = new Set(prev)
      if (next.has(clauseId)) {
        next.delete(clauseId)
      } else {
        next.add(clauseId)
      }
      return next
    })
  }

  useEffect(() => {
    const fetchData = async () => {
      try {
        setError(null)
        const doc = await api.documents.get(id)
        setDocument(doc)

        if (doc.status === 'completed') {
          const analysisData = await api.documents.getAnalysis(id)
          setAnalysis(analysisData)

          // Fetch versions separately (non-blocking)
          api.documents.getVersions(id)
            .then(versionsData => {
              console.log('Versions loaded:', versionsData.versions.length)
              setVersions(versionsData.versions)
            })
            .catch((err) => {
              console.error('Failed to load versions:', err)
              // Versions are optional, so don't block the page
            })
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load document')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [id])

  // Poll for updates if document is still processing
  // Uses a ref to prevent overlapping requests
  const isPollingRef = useRef(false)

  useEffect(() => {
    if (!document || !['uploaded', 'processing', 'extracting', 'analyzing'].includes(document.status)) {
      return
    }

    const poll = async () => {
      // Skip if a request is already in progress
      if (isPollingRef.current) return

      isPollingRef.current = true
      try {
        const doc = await api.documents.get(id)
        setDocument(doc)
        if (doc.status === 'completed') {
          const analysisData = await api.documents.getAnalysis(id)
          setAnalysis(analysisData)
          // Also fetch versions when processing completes
          const versionsData = await api.documents.getVersions(id)
          setVersions(versionsData.versions)
        }
      } catch {
        // Ignore polling errors
      } finally {
        isPollingRef.current = false
      }
    }

    const interval = setInterval(poll, 2000) // Poll every 2s with request deduplication

    return () => {
      clearInterval(interval)
      isPollingRef.current = false
    }
  }, [id, document])

  const handleReprocess = async () => {
    if (!document) return
    setReprocessing(true)
    try {
      // Clear analysis to show progress bar
      setAnalysis(null)
      // Update document status locally - start at extracting since file is already uploaded
      setDocument({ ...document, status: 'extracting' as const, status_message: 'Extracting text for reprocessing...' })
      showToast('Reprocessing started', 'success')

      // Fire and forget - let the API process in background
      // The polling useEffect will pick up status changes
      api.documents.process(document.id).catch((err) => {
        showToast(err instanceof Error ? err.message : 'Failed to reprocess document', 'error')
        // Refresh to get actual status on error
        api.documents.get(document.id).then(setDocument)
      })
    } finally {
      setReprocessing(false)
    }
  }

  const toggleVersionSelection = (versionId: string) => {
    setSelectedVersions((prev) => {
      if (prev.includes(versionId)) {
        return prev.filter((id) => id !== versionId)
      }
      if (prev.length >= 2) {
        // Replace the oldest selection
        return [prev[1], versionId]
      }
      return [...prev, versionId]
    })
  }

  const handleVersionUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !document) return

    setUploadingVersion(true)
    try {
      await api.documents.uploadVersion(document.id, file)
      // Clear analysis since new version needs processing
      setAnalysis(null)
      // Set status locally to show progress bar immediately (starts at extracting)
      setDocument({ ...document, status: 'extracting' as const, status_message: 'Processing new version...' })
      // Refresh versions list
      const versionsData = await api.documents.getVersions(document.id)
      setVersions(versionsData.versions)
      showToast('New version uploaded - processing started', 'success')
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to upload version', 'error')
    } finally {
      setUploadingVersion(false)
      // Reset the input
      if (versionFileInputRef.current) {
        versionFileInputRef.current.value = ''
      }
    }
  }

  const canCompare = selectedVersions.length === 2

  // Sort selected versions by version_number (older first) for comparison URL
  const sortedVersionIds = canCompare
    ? [...selectedVersions].sort((a, b) => {
        const vA = versions.find(v => v.id === a)
        const vB = versions.find(v => v.id === b)
        return (vA?.version_number || 0) - (vB?.version_number || 0)
      })
    : []

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 text-blue-600 animate-spin" />
      </div>
    )
  }

  if (error || !document) {
    return (
      <div className="max-w-4xl mx-auto">
        <Link
          href="/dashboard"
          className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-6"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Documents
        </Link>
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <AlertCircle className="h-8 w-8 text-red-500 mx-auto mb-3" />
          <p className="text-red-700">{error || 'Document not found'}</p>
        </div>
      </div>
    )
  }

  const isProcessing = ['uploaded', 'processing', 'extracting', 'analyzing'].includes(document.status)
  const isCompleted = document.status === 'completed'
  const isFailed = document.status === 'failed'

  const StatusIcon = isCompleted
    ? FileCheck
    : isFailed
    ? AlertTriangle
    : isProcessing
    ? Loader2
    : Clock

  return (
    <div className="max-w-4xl mx-auto">
      <Link
        href="/dashboard"
        className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-6"
      >
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back to Documents
      </Link>

      {/* Document Header */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-4">
            <div className="p-3 bg-blue-50 rounded-lg">
              <FileText className="h-8 w-8 text-blue-600" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-gray-900">
                {document.original_filename}
              </h1>
              <p className="text-sm text-gray-500 mt-1">
                {formatFileSize(document.file_size)} • {document.file_type?.toUpperCase() || 'FILE'} • Uploaded {formatDate(document.created_at)}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <div
              className={cn(
                'inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium',
                getStatusColor(document.status)
              )}
            >
              <StatusIcon
                className={cn('h-4 w-4 mr-1.5', isProcessing && 'animate-spin')}
              />
              {document.status.charAt(0).toUpperCase() + document.status.slice(1)}
            </div>

            {(isFailed || isCompleted) && (
              <button
                onClick={handleReprocess}
                disabled={reprocessing}
                className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
              >
                {reprocessing ? (
                  <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4 mr-1.5" />
                )}
                Reprocess
              </button>
            )}
          </div>
        </div>

        {document.status_message && (
          <p className="mt-4 text-sm text-gray-600 bg-gray-50 rounded-md px-3 py-2">
            {document.status_message}
          </p>
        )}

        {isCompleted && (
          <div className="mt-4 pt-4 border-t border-gray-100 flex items-center space-x-6 text-sm text-gray-500">
            {document.page_count && (
              <span>{document.page_count} pages</span>
            )}
            {document.word_count && (
              <span>{document.word_count.toLocaleString()} words</span>
            )}
            {document.chunk_count && (
              <span>{document.chunk_count} clauses analyzed</span>
            )}
          </div>
        )}
      </div>

      {/* Processing State */}
      {isProcessing && (() => {
        const progressMap: Record<string, number> = {
          uploaded: 5,
          processing: 15,
          extracting: 40,
          analyzing: 75,
        }
        const progress = progressMap[document.status] || 10
        const statusTextMap: Record<string, string> = {
          uploaded: 'Preparing document...',
          processing: 'Starting document processing...',
          extracting: 'Extracting text from your document...',
          analyzing: 'Running AI risk analysis on contract clauses...',
        }
        const statusText = statusTextMap[document.status] || 'Processing your document...'

        return (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
            <div className="flex items-center justify-center mb-4">
              <Loader2 className="h-8 w-8 text-blue-600 animate-spin" />
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2 text-center">
              Analyzing Document
            </h3>
            <p className="text-sm text-gray-600 text-center mb-4">
              {statusText}
            </p>

            {/* Progress Bar */}
            <div className="max-w-md mx-auto">
              <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                <span>{document.status.charAt(0).toUpperCase() + document.status.slice(1)}</span>
                <span>{progress}%</span>
              </div>
              <div className="h-2 bg-blue-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-600 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="flex justify-between text-xs text-gray-400 mt-2">
                <span>Upload</span>
                <span>Extract</span>
                <span>Analyze</span>
                <span>Complete</span>
              </div>
            </div>
          </div>
        )
      })()}

      {/* Failed State */}
      {isFailed && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <AlertTriangle className="h-8 w-8 text-red-500 mx-auto mb-3" />
          <h3 className="text-lg font-medium text-gray-900 mb-1">
            Processing Failed
          </h3>
          <p className="text-sm text-gray-600 mb-4">
            {document.status_message || 'An error occurred while processing your document.'}
          </p>
          <button
            onClick={handleReprocess}
            disabled={reprocessing}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
          >
            {reprocessing ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Try Again
          </button>
        </div>
      )}

      {/* Analysis Results */}
      {isCompleted && analysis && (
        <div className="space-y-6">
          {/* Risk Summary */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">
                Risk Summary
              </h2>
              {versions.length > 0 && (
                <span className="text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded">
                  Version {versions[0].version_number}
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {(['critical', 'high', 'medium', 'low'] as RiskLevel[]).map((level) => {
                const count = analysis.clauses.filter((c) => c.risk_level === level).length
                const Icon = riskIcons[level]
                return (
                  <div
                    key={level}
                    className={cn(
                      'rounded-lg p-4 text-center',
                      riskCardStyles[level]
                    )}
                  >
                    <Icon className={cn('h-6 w-6 mx-auto mb-2', riskIconStyles[level])} />
                    <p className={cn('text-2xl font-bold', riskIconStyles[level])}>{count}</p>
                    <p className="text-xs text-gray-700 font-medium">{riskLabels[level]}</p>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Version History & Comparison */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <History className="h-5 w-5 text-gray-500" />
                <h2 className="text-lg font-semibold text-gray-900">
                  Version History ({versions.length})
                </h2>
                <div className="relative">
                  <button
                    onClick={() => setShowVersionHelp(!showVersionHelp)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    <HelpCircle className="h-4 w-4" />
                  </button>
                  {showVersionHelp && (
                    <div className="absolute left-0 top-6 z-10 w-72 p-3 bg-white border border-gray-200 rounded-lg shadow-lg text-sm text-gray-600">
                      <p className="font-medium text-gray-900 mb-1">About Versions</p>
                      <p className="mb-2">Upload updated versions of this contract to track changes over time.</p>
                      <p className="text-xs text-gray-500">Select any 2 versions to compare clause-by-clause differences and risk changes.</p>
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {/* Hidden file input */}
                <input
                  ref={versionFileInputRef}
                  type="file"
                  accept=".pdf,.docx"
                  onChange={handleVersionUpload}
                  className="hidden"
                />
                <button
                  onClick={() => versionFileInputRef.current?.click()}
                  disabled={uploadingVersion}
                  className="inline-flex items-center px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
                >
                  {uploadingVersion ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Upload className="h-4 w-4 mr-2" />
                  )}
                  Upload New Version
                </button>
                {versions.length >= 2 && (
                  <Link
                    href={
                      canCompare
                        ? `/dashboard/documents/${id}/compare?v1=${sortedVersionIds[0]}&v2=${sortedVersionIds[1]}`
                        : '#'
                    }
                    className={cn(
                      'inline-flex items-center px-4 py-2 text-sm font-medium rounded-md',
                      canCompare
                        ? 'bg-blue-600 text-white hover:bg-blue-700'
                        : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    )}
                    onClick={(e) => !canCompare && e.preventDefault()}
                  >
                    <GitCompare className="h-4 w-4 mr-2" />
                    Compare Selected
                  </Link>
                )}
              </div>
            </div>

            {versions.length >= 2 && (
              <p className="text-sm text-gray-500 mb-4">
                Select 2 versions to compare. {selectedVersions.length}/2 selected.
              </p>
            )}

            {versions.length === 0 && (
              <div className="text-center py-6 text-gray-500">
                <History className="h-8 w-8 mx-auto mb-2 text-gray-400" />
                <p className="text-sm">No versions yet. Upload a new version to start tracking changes.</p>
              </div>
            )}

            {versions.length > 0 && (
              <div className="space-y-2">
                {versions.map((version) => {
                  const isSelected = selectedVersions.includes(version.id)
                  const selectionIndex = selectedVersions.indexOf(version.id)
                  return (
                    <div
                      key={version.id}
                      onClick={() => versions.length >= 2 && toggleVersionSelection(version.id)}
                      className={cn(
                        'flex items-center justify-between p-3 rounded-lg border transition-colors',
                        versions.length >= 2 && 'cursor-pointer',
                        isSelected
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                      )}
                    >
                      <div className="flex items-center gap-3">
                        {versions.length >= 2 && (
                          <div
                            className={cn(
                              'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold',
                              isSelected
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-200 text-gray-500'
                            )}
                          >
                            {isSelected ? selectionIndex + 1 : ''}
                          </div>
                        )}
                        <div>
                          <p className="font-medium text-gray-900">
                            Version {version.version_number}
                          </p>
                          <p className="text-sm text-gray-500">
                            {formatDate(version.created_at)}
                            {version.page_count && ` • ${version.page_count} pages`}
                            {version.word_count && ` • ${version.word_count.toLocaleString()} words`}
                          </p>
                        </div>
                      </div>
                      <ChevronRight className="h-5 w-5 text-gray-400" />
                    </div>
                  )
                })}
              </div>
            )}

            {versions.length === 1 && (
              <p className="text-sm text-gray-500 mt-4 text-center">
                Upload another version to enable comparison.
              </p>
            )}
          </div>

          {/* Clauses List */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">
                Analyzed Clauses ({analysis.clauses.length})
              </h2>
              {versions.length > 0 && (
                <span className="text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded">
                  Version {versions[0].version_number}
                </span>
              )}
            </div>

            {/* Risk Level Filter */}
            <div className="flex flex-wrap gap-2 mb-4 pb-4 border-b border-gray-200">
              {(['all', 'critical', 'high', 'medium', 'low'] as const).map((level) => {
                const count = level === 'all'
                  ? analysis.clauses.length
                  : analysis.clauses.filter((c) => c.risk_level === level).length
                const isActive = riskFilter === level
                return (
                  <button
                    key={level}
                    onClick={() => setRiskFilter(level)}
                    className={cn(
                      'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                      isActive
                        ? level === 'all'
                          ? 'bg-gray-900 text-white'
                          : level === 'critical'
                          ? 'bg-red-600 text-white'
                          : level === 'high'
                          ? 'bg-orange-500 text-white'
                          : level === 'medium'
                          ? 'bg-yellow-500 text-white'
                          : 'bg-green-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    )}
                  >
                    {level === 'all' ? 'All' : level.charAt(0).toUpperCase() + level.slice(1)} ({count})
                  </button>
                )
              })}
            </div>

            <div className="space-y-4">
              {analysis.clauses.length === 0 ? (
                <p className="text-gray-500 text-center py-4">
                  No clauses found in this document.
                </p>
              ) : (
                (() => {
                  const filteredClauses = analysis.clauses.filter(
                    (clause) => riskFilter === 'all' || clause.risk_level === riskFilter
                  )
                  if (filteredClauses.length === 0) {
                    return (
                      <p className="text-gray-500 text-center py-4">
                        No {riskFilter} risk clauses found.
                      </p>
                    )
                  }
                  return filteredClauses.map((clause) => {
                    const Icon = riskIcons[clause.risk_level]
                  const isExpanded = expandedClauses.has(clause.id)
                  const isLongText = clause.text.length > 200
                  return (
                    <div
                      key={clause.id}
                      className={cn(
                        'border border-gray-200 rounded-lg p-4 bg-white',
                        riskBorderStyles[clause.risk_level]
                      )}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <h3 className="font-medium text-gray-900 capitalize">
                          {clause.clause_type?.replace(/_/g, ' ') || 'General Clause'}
                        </h3>
                        <div
                          className={cn(
                            'inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold',
                            riskBadgeStyles[clause.risk_level]
                          )}
                        >
                          <Icon className="h-3 w-3 mr-1" />
                          {clause.risk_level.charAt(0).toUpperCase() + clause.risk_level.slice(1)}
                        </div>
                      </div>

                      <p className={cn(
                        'text-sm text-gray-600',
                        !isExpanded && isLongText && 'line-clamp-3'
                      )}>
                        {clause.text}
                      </p>

                      {isLongText && (
                        <button
                          onClick={() => toggleClauseExpanded(clause.id)}
                          className="mt-2 mb-3 inline-flex items-center text-sm text-blue-600 hover:text-blue-800 font-medium"
                        >
                          {isExpanded ? (
                            <>
                              <ChevronUp className="h-4 w-4 mr-1" />
                              Show less
                            </>
                          ) : (
                            <>
                              <ChevronDown className="h-4 w-4 mr-1" />
                              Show more
                            </>
                          )}
                        </button>
                      )}

                      {!isLongText && <div className="mb-3" />}

                      {clause.risk_explanation && (
                        <div className="bg-gray-50 rounded-md p-3 mb-3">
                          <p className="text-sm text-gray-700">
                            <span className="font-medium">Analysis: </span>
                            {clause.risk_explanation}
                          </p>
                        </div>
                      )}

                      {clause.recommendations && clause.recommendations.length > 0 && (
                        <div className="border-t border-gray-100 pt-3">
                          <p className="text-xs font-medium text-gray-500 mb-2">
                            Recommendations:
                          </p>
                          <ul className="text-sm text-gray-600 space-y-1">
                            {clause.recommendations.map((rec, idx) => (
                              <li key={idx} className="flex items-start">
                                <span className="text-blue-500 mr-2">•</span>
                                {rec}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                    )
                  })
                })()
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
