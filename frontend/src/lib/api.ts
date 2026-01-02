import { createClient } from '@/lib/supabase/client'
import type {
  Document,
  DocumentListResponse,
  DocumentAnalysis,
  VersionListResponse,
  ComparisonResult,
  SearchResponse,
} from '@/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Cache for auth token to avoid repeated getSession calls
let cachedToken: string | null = null
let tokenExpiry: number = 0

async function getAuthHeaders(): Promise<HeadersInit> {
  // Use cached token if still valid (with 60 second buffer)
  const now = Date.now()
  if (cachedToken && tokenExpiry > now + 60000) {
    return {
      'Authorization': `Bearer ${cachedToken}`,
      'Content-Type': 'application/json',
    }
  }

  const supabase = createClient()
  const { data: { session } } = await supabase.auth.getSession()

  if (!session?.access_token) {
    cachedToken = null
    tokenExpiry = 0
    throw new Error('Not authenticated')
  }

  // Cache the token
  cachedToken = session.access_token
  tokenExpiry = session.expires_at ? session.expires_at * 1000 : now + 3600000

  return {
    'Authorization': `Bearer ${cachedToken}`,
    'Content-Type': 'application/json',
  }
}

async function fetchWithAuth<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = await getAuthHeaders()

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      ...headers,
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

export const api = {
  documents: {
    list: async (): Promise<DocumentListResponse> => {
      return fetchWithAuth<DocumentListResponse>('/api/v1/documents')
    },

    get: async (id: string): Promise<Document> => {
      return fetchWithAuth<Document>(`/api/v1/documents/${id}`)
    },

    getAnalysis: async (id: string): Promise<DocumentAnalysis> => {
      return fetchWithAuth<DocumentAnalysis>(`/api/v1/documents/${id}/analysis`)
    },

    upload: async (file: File): Promise<Document> => {
      const supabase = createClient()
      const { data: { session } } = await supabase.auth.getSession()

      if (!session?.access_token) {
        throw new Error('Not authenticated')
      }

      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`${API_URL}/api/v1/documents/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: formData,
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
        throw new Error(error.detail || `HTTP ${response.status}`)
      }

      return response.json()
    },

    delete: async (id: string): Promise<void> => {
      const headers = await getAuthHeaders()

      const response = await fetch(`${API_URL}/api/v1/documents/${id}`, {
        method: 'DELETE',
        headers,
      })

      if (!response.ok && response.status !== 204) {
        const error = await response.json().catch(() => ({ detail: 'Delete failed' }))
        throw new Error(error.detail || `HTTP ${response.status}`)
      }
    },

    process: async (id: string): Promise<Document> => {
      return fetchWithAuth<Document>(`/api/v1/documents/${id}/process`, {
        method: 'POST',
      })
    },

    getVersions: async (id: string): Promise<VersionListResponse> => {
      return fetchWithAuth<VersionListResponse>(`/api/v1/documents/${id}/versions`)
    },

    uploadVersion: async (id: string, file: File): Promise<void> => {
      const supabase = createClient()
      const { data: { session } } = await supabase.auth.getSession()

      if (!session?.access_token) {
        throw new Error('Not authenticated')
      }

      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`${API_URL}/api/v1/documents/${id}/versions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: formData,
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
        throw new Error(error.detail || `HTTP ${response.status}`)
      }
    },
  },

  compare: {
    versions: async (version1: string, version2: string): Promise<ComparisonResult> => {
      return fetchWithAuth<ComparisonResult>(
        `/api/v1/compare?version1=${version1}&version2=${version2}`
      )
    },
  },

  search: {
    clauses: async (
      query: string,
      options?: { limit?: number; minSimilarity?: number; documentId?: string }
    ): Promise<SearchResponse> => {
      const params = new URLSearchParams({ q: query })
      if (options?.limit) params.append('limit', options.limit.toString())
      if (options?.minSimilarity) params.append('min_similarity', options.minSimilarity.toString())
      if (options?.documentId) params.append('document_id', options.documentId)

      return fetchWithAuth<SearchResponse>(`/api/v1/search?${params}`)
    },
  },
}
