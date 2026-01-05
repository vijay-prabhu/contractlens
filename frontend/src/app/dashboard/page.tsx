'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import Link from 'next/link'
import { Upload, FileText, RefreshCw, AlertCircle } from 'lucide-react'
import { api } from '@/lib/api'
import { DocumentCard } from '@/components/document-card'
import { useToast } from '@/components/toast'
import type { Document } from '@/types'

export default function DashboardPage() {
  const { showToast } = useToast()
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  // Use ref to track documents for polling without triggering re-renders
  const documentsRef = useRef<Document[]>([])

  const fetchDocuments = useCallback(async () => {
    try {
      setError(null)
      const response = await api.documents.list()
      setDocuments(response.documents)
      documentsRef.current = response.documents
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDocuments()

    // Poll for updates on processing documents (every 10 seconds)
    const interval = setInterval(() => {
      const hasProcessing = documentsRef.current.some((doc) =>
        ['uploaded', 'processing', 'extracting', 'analyzing'].includes(doc.status)
      )
      if (hasProcessing) {
        fetchDocuments()
      }
    }, 10000)

    return () => clearInterval(interval)
  }, [fetchDocuments])

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this document?')) {
      return
    }

    setDeleting(id)
    try {
      await api.documents.delete(id)
      setDocuments((prev) => prev.filter((doc) => doc.id !== id))
      showToast('Document deleted successfully', 'success')
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to delete document', 'error')
    } finally {
      setDeleting(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 text-blue-600 animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <AlertCircle className="h-8 w-8 text-red-500 mx-auto mb-3" />
        <p className="text-red-700">{error}</p>
        <button
          onClick={() => {
            setLoading(true)
            fetchDocuments()
          }}
          className="mt-4 text-sm text-red-600 hover:text-red-700 underline"
        >
          Try again
        </button>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Documents</h1>
          <p className="text-gray-500 mt-1">
            Upload and analyze your contracts
          </p>
        </div>
        <Link
          href="/dashboard/upload"
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
        >
          <Upload className="h-4 w-4 mr-2" />
          Upload Document
        </Link>
      </div>

      {documents.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            No documents yet
          </h3>
          <p className="text-gray-500 mb-6">
            Upload your first contract to get started with AI-powered analysis.
          </p>
          <Link
            href="/dashboard/upload"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
          >
            <Upload className="h-4 w-4 mr-2" />
            Upload Document
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {documents.map((document) => (
            <DocumentCard
              key={document.id}
              document={document}
              onDelete={deleting === document.id ? undefined : handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  )
}
