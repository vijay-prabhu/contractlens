'use client'

import { useState, useEffect } from 'react'
import { useParams, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft,
  GitCompare,
  Plus,
  Minus,
  RefreshCw,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  Info,
  TrendingUp,
  TrendingDown,
  Loader2,
  FileText,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { ComparisonResult, ClauseChange } from '@/types'

const riskIcons: Record<string, typeof AlertTriangle> = {
  critical: AlertTriangle,
  high: AlertCircle,
  medium: Info,
  low: CheckCircle,
}

const riskColors: Record<string, string> = {
  critical: 'text-red-600 bg-red-50 border-red-200',
  high: 'text-orange-600 bg-orange-50 border-orange-200',
  medium: 'text-yellow-600 bg-yellow-50 border-yellow-200',
  low: 'text-green-600 bg-green-50 border-green-200',
}

const changeTypeColors: Record<string, { bg: string; border: string; text: string; icon: typeof Plus }> = {
  added: { bg: 'bg-green-50', border: 'border-l-4 border-l-green-500', text: 'text-green-700', icon: Plus },
  removed: { bg: 'bg-red-50', border: 'border-l-4 border-l-red-500', text: 'text-red-700', icon: Minus },
  modified: { bg: 'bg-blue-50', border: 'border-l-4 border-l-blue-500', text: 'text-blue-700', icon: RefreshCw },
  unchanged: { bg: 'bg-gray-50', border: 'border-l-4 border-l-gray-300', text: 'text-gray-600', icon: CheckCircle },
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

function SummaryCard({
  title,
  value,
  icon: Icon,
  color,
  subtitle,
}: {
  title: string
  value: number | string
  icon: typeof Plus
  color: string
  subtitle?: string
}) {
  return (
    <div className={cn('rounded-lg p-4 border', color)}>
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-full bg-white/50">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-2xl font-bold">{value}</p>
          <p className="text-sm font-medium">{title}</p>
          {subtitle && <p className="text-xs opacity-75">{subtitle}</p>}
        </div>
      </div>
    </div>
  )
}

function RiskTrendIndicator({ trend, oldScore, newScore }: { trend: string; oldScore: number; newScore: number }) {
  const TrendIcon = trend === 'increased' ? TrendingUp : trend === 'decreased' ? TrendingDown : RefreshCw
  const trendColor =
    trend === 'increased'
      ? 'text-red-600 bg-red-50'
      : trend === 'decreased'
      ? 'text-green-600 bg-green-50'
      : 'text-gray-600 bg-gray-50'

  return (
    <div className={cn('rounded-lg p-4 border', trendColor)}>
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-full bg-white/50">
          <TrendIcon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-medium">Risk Score</p>
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold">{oldScore.toFixed(1)}</span>
            <span className="text-gray-400">→</span>
            <span className="text-lg font-bold">{newScore.toFixed(1)}</span>
          </div>
          <p className="text-xs capitalize">{trend}</p>
        </div>
      </div>
    </div>
  )
}

function ClauseChangeCard({ change, expanded, onToggle }: { change: ClauseChange; expanded: boolean; onToggle: () => void }) {
  const style = changeTypeColors[change.change_type]
  const Icon = style.icon
  const OldRiskIcon = change.old_risk_level ? riskIcons[change.old_risk_level] || Info : Info
  const NewRiskIcon = change.new_risk_level ? riskIcons[change.new_risk_level] || Info : Info

  return (
    <div className={cn('rounded-lg border border-gray-200 overflow-hidden', style.border)}>
      {/* Header */}
      <button
        onClick={onToggle}
        className={cn('w-full px-4 py-3 flex items-center justify-between', style.bg)}
      >
        <div className="flex items-center gap-3">
          <Icon className={cn('h-4 w-4', style.text)} />
          <span className="font-medium text-gray-900">
            {clauseTypeLabels[change.clause_type] || change.clause_type}
          </span>
          <span className={cn('text-xs font-semibold px-2 py-0.5 rounded capitalize', style.bg, style.text)}>
            {change.change_type}
          </span>
          {change.similarity_score !== undefined && change.change_type === 'modified' && (
            <span className="text-xs text-gray-500">
              {Math.round(change.similarity_score * 100)}% similar
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {/* Risk indicators */}
          {change.change_type === 'modified' && change.old_risk_level && change.new_risk_level && (
            <div className="flex items-center gap-2 text-xs">
              <span className={cn('px-2 py-0.5 rounded flex items-center gap-1', riskColors[change.old_risk_level])}>
                <OldRiskIcon className="h-3 w-3" />
                {change.old_risk_level}
              </span>
              <span className="text-gray-400">→</span>
              <span className={cn('px-2 py-0.5 rounded flex items-center gap-1', riskColors[change.new_risk_level])}>
                <NewRiskIcon className="h-3 w-3" />
                {change.new_risk_level}
              </span>
            </div>
          )}
          {change.change_type === 'added' && change.new_risk_level && (
            <span className={cn('px-2 py-0.5 rounded text-xs flex items-center gap-1', riskColors[change.new_risk_level])}>
              <NewRiskIcon className="h-3 w-3" />
              {change.new_risk_level}
            </span>
          )}
          {change.change_type === 'removed' && change.old_risk_level && (
            <span className={cn('px-2 py-0.5 rounded text-xs flex items-center gap-1', riskColors[change.old_risk_level])}>
              <OldRiskIcon className="h-3 w-3" />
              {change.old_risk_level}
            </span>
          )}
          {expanded ? <ChevronUp className="h-4 w-4 text-gray-400" /> : <ChevronDown className="h-4 w-4 text-gray-400" />}
        </div>
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="p-4 bg-white">
          {change.change_type === 'modified' ? (
            <div className="grid grid-cols-2 gap-4">
              {/* Old version */}
              <div>
                <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Previous Version</h4>
                <div className="p-3 bg-red-50 rounded border border-red-100 text-sm text-gray-700">
                  {change.old_text}
                </div>
              </div>
              {/* New version */}
              <div>
                <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Current Version</h4>
                <div className="p-3 bg-green-50 rounded border border-green-100 text-sm text-gray-700">
                  {change.new_text}
                </div>
              </div>
            </div>
          ) : change.change_type === 'added' ? (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Added Clause</h4>
              <div className="p-3 bg-green-50 rounded border border-green-100 text-sm text-gray-700">
                {change.new_text}
              </div>
            </div>
          ) : change.change_type === 'removed' ? (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Removed Clause</h4>
              <div className="p-3 bg-red-50 rounded border border-red-100 text-sm text-gray-700">
                {change.old_text}
              </div>
            </div>
          ) : (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Unchanged Clause</h4>
              <div className="p-3 bg-gray-50 rounded border border-gray-100 text-sm text-gray-700">
                {change.new_text || change.old_text}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function ComparePage() {
  const params = useParams()
  const searchParams = useSearchParams()
  const documentId = params.id as string
  const version1 = searchParams.get('v1')
  const version2 = searchParams.get('v2')

  const [comparison, setComparison] = useState<ComparisonResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedClauses, setExpandedClauses] = useState<Set<number>>(new Set())
  const [filterType, setFilterType] = useState<string>('all')

  useEffect(() => {
    const loadComparison = async () => {
      if (!version1 || !version2) {
        setError('Missing version parameters')
        setLoading(false)
        return
      }

      try {
        const result = await api.compare.versions(version1, version2)
        setComparison(result)
        // Auto-expand clauses with changes
        const changedIndices = new Set<number>()
        result.clause_changes.forEach((change, index) => {
          if (change.change_type !== 'unchanged') {
            changedIndices.add(index)
          }
        })
        setExpandedClauses(changedIndices)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load comparison')
      } finally {
        setLoading(false)
      }
    }

    loadComparison()
  }, [version1, version2])

  const toggleClause = (index: number) => {
    setExpandedClauses((prev) => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }

  const filteredChanges = comparison?.clause_changes.filter((change) => {
    if (filterType === 'all') return change.change_type !== 'unchanged'
    return change.change_type === filterType
  }) || []

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Loader2 className="h-8 w-8 text-blue-600 animate-spin mx-auto mb-3" />
          <p className="text-gray-600">Loading comparison...</p>
        </div>
      </div>
    )
  }

  if (error || !comparison) {
    return (
      <div className="max-w-4xl mx-auto">
        <Link
          href={`/dashboard/documents/${documentId}`}
          className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to document
        </Link>
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <AlertCircle className="h-8 w-8 text-red-500 mx-auto mb-3" />
          <p className="text-red-700">{error || 'Comparison not found'}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Link
          href={`/dashboard/documents/${documentId}`}
          className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to document
        </Link>

        <div className="flex items-center gap-3">
          <GitCompare className="h-6 w-6 text-blue-600" />
          <h1 className="text-2xl font-bold text-gray-900">Version Comparison</h1>
        </div>
        <p className="mt-1 text-gray-600">
          Comparing Version {comparison.version1_number} → Version {comparison.version2_number}
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <SummaryCard
          title="Added"
          value={comparison.clauses_added}
          icon={Plus}
          color="text-green-700 bg-green-50 border-green-200"
          subtitle="new clauses"
        />
        <SummaryCard
          title="Removed"
          value={comparison.clauses_removed}
          icon={Minus}
          color="text-red-700 bg-red-50 border-red-200"
          subtitle="deleted clauses"
        />
        <SummaryCard
          title="Modified"
          value={comparison.clauses_modified}
          icon={RefreshCw}
          color="text-blue-700 bg-blue-50 border-blue-200"
          subtitle="changed clauses"
        />
        <SummaryCard
          title="Unchanged"
          value={comparison.clauses_unchanged}
          icon={CheckCircle}
          color="text-gray-700 bg-gray-50 border-gray-200"
          subtitle="same clauses"
        />
        <RiskTrendIndicator
          trend={comparison.risk_summary.risk_trend}
          oldScore={comparison.risk_summary.old_overall_score}
          newScore={comparison.risk_summary.new_overall_score}
        />
      </div>

      {/* Risk Summary Details */}
      {(comparison.risk_summary.critical_added > 0 ||
        comparison.risk_summary.critical_removed > 0 ||
        comparison.risk_summary.high_risk_added > 0 ||
        comparison.risk_summary.high_risk_removed > 0) && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-8">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-medium text-amber-900">Risk Changes</h3>
              <ul className="mt-2 space-y-1 text-sm text-amber-800">
                {comparison.risk_summary.critical_added > 0 && (
                  <li>+{comparison.risk_summary.critical_added} critical risk clause(s) added</li>
                )}
                {comparison.risk_summary.critical_removed > 0 && (
                  <li>-{comparison.risk_summary.critical_removed} critical risk clause(s) removed</li>
                )}
                {comparison.risk_summary.high_risk_added > 0 && (
                  <li>+{comparison.risk_summary.high_risk_added} high risk clause(s) added</li>
                )}
                {comparison.risk_summary.high_risk_removed > 0 && (
                  <li>-{comparison.risk_summary.high_risk_removed} high risk clause(s) removed</li>
                )}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Text Diff Summary */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-8">
        <div className="flex items-center gap-3">
          <FileText className="h-5 w-5 text-gray-600" />
          <div>
            <h3 className="font-medium text-gray-900">Text Changes</h3>
            <p className="text-sm text-gray-600">
              <span className="text-green-600 font-medium">+{comparison.text_diff.additions}</span> additions,{' '}
              <span className="text-red-600 font-medium">-{comparison.text_diff.deletions}</span> deletions
            </p>
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 mb-4 border-b border-gray-200 pb-4">
        <span className="text-sm font-medium text-gray-700">Filter:</span>
        {[
          { key: 'all', label: 'All Changes', count: comparison.clauses_added + comparison.clauses_removed + comparison.clauses_modified },
          { key: 'added', label: 'Added', count: comparison.clauses_added },
          { key: 'removed', label: 'Removed', count: comparison.clauses_removed },
          { key: 'modified', label: 'Modified', count: comparison.clauses_modified },
          { key: 'unchanged', label: 'Unchanged', count: comparison.clauses_unchanged },
        ].map((filter) => (
          <button
            key={filter.key}
            onClick={() => setFilterType(filter.key)}
            className={cn(
              'px-3 py-1.5 text-sm rounded-full transition-colors',
              filterType === filter.key
                ? 'bg-blue-100 text-blue-700 font-medium'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            {filter.label} ({filter.count})
          </button>
        ))}
      </div>

      {/* Clause Changes List */}
      <div className="space-y-3">
        {filteredChanges.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No {filterType === 'all' ? 'changes' : filterType} clauses found
          </div>
        ) : (
          filteredChanges.map((change, index) => (
            <ClauseChangeCard
              key={`${change.change_type}-${change.clause_type}-${index}`}
              change={change}
              expanded={expandedClauses.has(comparison.clause_changes.indexOf(change))}
              onToggle={() => toggleClause(comparison.clause_changes.indexOf(change))}
            />
          ))
        )}
      </div>
    </div>
  )
}
