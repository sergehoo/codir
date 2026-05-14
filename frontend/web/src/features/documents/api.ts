import { apiClient } from '@/api/client'

export type DocumentItem = {
  id: string
  name: string
  file: string
  mime: string
  size_bytes: number
  is_confidential: boolean
  uploaded_by: string | null
  download_url?: string | null
  created_at: string
}

export const documentsApi = {
  list: async () => {
    const r = await apiClient.get<DocumentItem[] | { results: DocumentItem[] }>('/documents/')
    return r.data
  },
  upload: async (file: File, isConfidential: boolean) => {
    const form = new FormData()
    form.append('name', file.name)
    form.append('file', file)
    form.append('is_confidential', isConfidential ? 'true' : 'false')
    const r = await apiClient.post<DocumentItem>('/documents/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return r.data
  },
  remove: async (id: string) => (await apiClient.delete(`/documents/${id}/`)).data,
}

export const documentsKeys = {
  all: ['documents'] as const,
  list: () => [...documentsKeys.all, 'list'] as const,
}

export function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`
  return `${(b / 1024 / 1024 / 1024).toFixed(1)} GB`
}
