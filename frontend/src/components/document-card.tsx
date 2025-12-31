'use client'

import Link from 'next/link'
import { FileText, Clock, FileCheck, AlertTriangle, Loader2, Trash2 } from 'lucide-react'
import { cn, formatDate, formatFileSize, getStatusColor } from '@/lib/utils'
import type { Document } from '@/types'

interface DocumentCardProps {
  document: Document
  onDelete?: (id: string) => void
}

export function DocumentCard({ document, onDelete }: DocumentCardProps) {
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
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
      <div className="p-5">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-blue-50 rounded-lg">
              <FileText className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <Link
                href={`/dashboard/documents/${document.id}`}
                className="text-sm font-medium text-gray-900 hover:text-blue-600 line-clamp-1"
              >
                {document.original_filename}
              </Link>
              <p className="text-xs text-gray-500 mt-0.5">
                {formatFileSize(document.file_size)} • {document.file_type.toUpperCase()}
              </p>
            </div>
          </div>

          {onDelete && (
            <button
              onClick={(e) => {
                e.preventDefault()
                onDelete(document.id)
              }}
              className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors"
              title="Delete document"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>

        <div className="mt-4 flex items-center justify-between">
          <div
            className={cn(
              'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium',
              getStatusColor(document.status)
            )}
          >
            <StatusIcon
              className={cn('h-3 w-3 mr-1', isProcessing && 'animate-spin')}
            />
            {document.status.charAt(0).toUpperCase() + document.status.slice(1)}
          </div>

          <span className="text-xs text-gray-500">
            {formatDate(document.created_at)}
          </span>
        </div>

        {document.status_message && (
          <p className="mt-2 text-xs text-gray-500 line-clamp-1">
            {document.status_message}
          </p>
        )}

        {isCompleted && (
          <div className="mt-3 pt-3 border-t border-gray-100 flex items-center space-x-4 text-xs text-gray-500">
            {document.page_count && (
              <span>{document.page_count} pages</span>
            )}
            {document.word_count && (
              <span>{document.word_count.toLocaleString()} words</span>
            )}
            {document.chunk_count && (
              <span>{document.chunk_count} clauses</span>
            )}
          </div>
        )}
      </div>

      {isCompleted && (
        <Link
          href={`/dashboard/documents/${document.id}`}
          className="block px-5 py-3 bg-gray-50 border-t border-gray-100 text-sm text-center text-blue-600 hover:text-blue-700 hover:bg-gray-100 rounded-b-lg"
        >
          View Analysis
        </Link>
      )}
    </div>
  )
}
