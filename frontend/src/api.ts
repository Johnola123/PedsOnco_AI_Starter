export type Health = {
  status: string
  database: string
  object_storage: string
}

export type Dataset = {
  id: number
  project_name: string
  original_name: string
  content_type: string | null
  size_bytes: number
  sha256: string
  object_key: string
  status: string
  created_at: string
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export async function getHealth(): Promise<Health> {
  const response = await fetch(`${API_BASE}/health`)
  if (!response.ok) throw new Error('API health check failed')
  return response.json()
}

export async function getDatasets(): Promise<Dataset[]> {
  const response = await fetch(`${API_BASE}/datasets`)
  if (!response.ok) throw new Error('Could not load datasets')
  return response.json()
}

export async function uploadDataset(file: File, projectName: string): Promise<Dataset> {
  const form = new FormData()
  form.append('file', file)
  form.append('project_name', projectName)

  const response = await fetch(`${API_BASE}/datasets/upload`, {
    method: 'POST',
    body: form,
  })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || 'Upload failed')
  }
  return response.json()
}
