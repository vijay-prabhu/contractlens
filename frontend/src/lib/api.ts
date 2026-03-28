import * as Sentry from '@sentry/nextjs'
import { createClient } from '@/lib/supabase/client'
import type {
  Document,
  DocumentListResponse,
  DocumentAnalysis,
  VersionListResponse,
  ComparisonResult,
  SearchResponse,
} from '@/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8200'

// Encapsulated token cache with cleanup support
const tokenCache = {
  token: null as string | null,
  expiry: 0,
  clear() {
    this.token = null
    this.expiry = 0
  },
}

async function getAuthToken(): Promise<string> {
  const now = Date.now()
  if (tokenCache.token && tokenCache.expiry > now + 60000) {
    return tokenCache.token
  }

  const supabase = createClient()
  const { data: { session } } = await supabase.auth.getSession()

  if (!session?.access_token) {
    tokenCache.clear()
    Sentry.setUser(null)
    throw new Error('Not authenticated')
  }

  if (session.user) {
    Sentry.setUser({ id: session.user.id, email: session.user.email ?? undefined })
  }

  tokenCache.token = session.access_token
  tokenCache.expiry = session.expires_at ? session.expires_at * 1000 : now + 3600000

  return tokenCache.token
}

async function getAuthHeaders(): Promise<HeadersInit> {
  const token = await getAuthToken()
  return {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  }
}

async function uploadWithAuth(url: string, formData: FormData, endpoint: string): Promise<Response> {
  const token = await getAuthToken()
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
    const message = error.detail || `HTTP ${response.status}`
    Sentry.captureException(new Error(message), {
      tags: { endpoint, http_status: response.status },
    })
    throw new Error(message)
  }

  return response
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
    const message = error.detail || `HTTP ${response.status}`
    Sentry.captureException(new Error(message), {
      tags: { endpoint, http_status: response.status },
    })
    throw new Error(message)
  }

  return response.json()
}

export function clearTokenCache() {
  tokenCache.clear()
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
      const formData = new FormData()
      formData.append('file', file)
      const response = await uploadWithAuth(
        `${API_URL}/api/v1/documents/upload`,
        formData,
        '/api/v1/documents/upload',
      )
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
        const message = error.detail || `HTTP ${response.status}`
        Sentry.captureException(new Error(message), {
          tags: { endpoint: `/api/v1/documents/${id}`, http_status: response.status },
        })
        throw new Error(message)
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
      const formData = new FormData()
      formData.append('file', file)
      await uploadWithAuth(
        `${API_URL}/api/v1/documents/${id}/versions`,
        formData,
        `/api/v1/documents/${id}/versions`,
      )
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
