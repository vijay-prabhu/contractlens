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
  Upload,
  HelpCircle,
} from 'lucide-react'
import { api } from '@/lib/api'
import { cn, formatDate, formatFileSize, getStatusColor } from '@/lib/utils'
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
  const [document, setDocument] = useState<Document | null>(null)
  const [analysis, setAnalysis] = useState<DocumentAnalysis | null>(null)
  const [versions, setVersions] = useState<DocumentVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reprocessing, setReprocessing] = useState(false)
  const [selectedVersions, setSelectedVersions] = useState<string[]>([])
  const [uploadingVersion, setUploadingVersion] = useState(false)
  const [showVersionHelp, setShowVersionHelp] = useState(false)
  const versionFileInputRef = useRef<HTMLInputElement>(null)

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
            .then(versionsData => setVersions(versionsData.versions))
            .catch(() => {/* Versions are optional */})
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
  useEffect(() => {
    if (!document || !['uploaded', 'processing', 'extracting', 'analyzing'].includes(document.status)) {
      return
    }

    const interval = setInterval(async () => {
      try {
        const doc = await api.documents.get(id)
        setDocument(doc)
        if (doc.status === 'completed') {
          const analysisData = await api.documents.getAnalysis(id)
          setAnalysis(analysisData)
        }
      } catch {
        // Ignore polling errors
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [id, document])

  const handleReprocess = async () => {
    if (!document) return
    setReprocessing(true)
    try {
      const updated = await api.documents.process(document.id)
      setDocument(updated)
      setAnalysis(null)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to reprocess document')
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
      // Refresh versions list
      const versionsData = await api.documents.getVersions(document.id)
      setVersions(versionsData.versions)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to upload version')
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

  const isProcessing = ['processing', 'extracting', 'analyzing'].includes(document.status)
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
                {formatFileSize(document.file_size)} • {document.file_type.toUpperCase()} • Uploaded {formatDate(document.created_at)}
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
      {isProcessing && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
          <Loader2 className="h-8 w-8 text-blue-600 animate-spin mx-auto mb-3" />
          <h3 className="text-lg font-medium text-gray-900 mb-1">
            Analyzing Document
          </h3>
          <p className="text-sm text-gray-600">
            {document.status === 'extracting'
              ? 'Extracting text from your document...'
              : document.status === 'analyzing'
              ? 'Running AI risk analysis on contract clauses...'
              : 'Processing your document...'}
          </p>
        </div>
      )}

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
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Risk Summary
            </h2>
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
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Analyzed Clauses ({analysis.clauses.length})
            </h2>
            <div className="space-y-4">
              {analysis.clauses.length === 0 ? (
                <p className="text-gray-500 text-center py-4">
                  No clauses found in this document.
                </p>
              ) : (
                analysis.clauses.map((clause) => {
                  const Icon = riskIcons[clause.risk_level]
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

                      <p className="text-sm text-gray-600 mb-3 line-clamp-3">
                        {clause.text}
                      </p>

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
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
