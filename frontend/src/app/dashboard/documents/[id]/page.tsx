'use client'

import { useEffect, useState } from 'react'
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
} from 'lucide-react'
import { api } from '@/lib/api'
import { cn, formatDate, formatFileSize, getStatusColor } from '@/lib/utils'
import type { Document, DocumentAnalysis, RiskLevel } from '@/types'

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
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reprocessing, setReprocessing] = useState(false)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setError(null)
        const doc = await api.documents.get(id)
        setDocument(doc)

        if (doc.status === 'completed') {
          const analysisData = await api.documents.getAnalysis(id)
          setAnalysis(analysisData)
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
