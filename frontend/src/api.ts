export type Health = {
  status: string
  database: string
  object_storage: string
  direct_uploads: boolean
  url_imports: boolean
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

type PresignResponse = {
  object_key: string
  upload_url: string
  method: 'PUT'
  headers: Record<string, string>
  expires_in: number
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

async function apiJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    const text = await response.text()
    let message = text || `Request failed (${response.status})`
    try {
      const parsed = JSON.parse(text)
      if (parsed?.detail) message = String(parsed.detail)
    } catch {
      // Keep text response.
    }
    throw new Error(message)
  }
  return response.json()
}

export async function getHealth(): Promise<Health> {
  return apiJson(`${API_BASE}/health`)
}

export async function getDatasets(): Promise<Dataset[]> {
  return apiJson(`${API_BASE}/datasets`)
}

export async function requestUploadUrl(file: File, projectName: string): Promise<PresignResponse> {
  return apiJson(`${API_BASE}/uploads/presign`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_name: projectName,
      filename: file.name,
      content_type: file.type || 'application/octet-stream',
    }),
  })
}

export function putFileDirect(
  file: File,
  presigned: PresignResponse,
  onProgress?: (percent: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', presigned.upload_url, true)
    Object.entries(presigned.headers).forEach(([key, value]) => xhr.setRequestHeader(key, value))
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    }
    xhr.onerror = () => reject(new Error('Direct upload to object storage failed. Check MinIO/S3 reachability and CORS.'))
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve()
      else reject(new Error(`Object-storage upload failed (${xhr.status}).`))
    }
    xhr.send(file)
  })
}

export async function completeDirectUpload(
  file: File,
  projectName: string,
  objectKey: string,
): Promise<Dataset> {
  return apiJson(`${API_BASE}/uploads/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_name: projectName,
      filename: file.name,
      object_key: objectKey,
      content_type: file.type || 'application/octet-stream',
    }),
  })
}

export async function uploadFileDirect(
  file: File,
  projectName: string,
  onProgress?: (percent: number) => void,
): Promise<Dataset> {
  const presigned = await requestUploadUrl(file, projectName)
  await putFileDirect(file, presigned, onProgress)
  return completeDirectUpload(file, projectName, presigned.object_key)
}

export async function importExternalUrl(params: {
  projectName: string
  url: string
  filename?: string
  bearerToken?: string
}): Promise<Dataset> {
  return apiJson(`${API_BASE}/import/url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_name: params.projectName,
      url: params.url,
      filename: params.filename || null,
      bearer_token: params.bearerToken || null,
    }),
  })
}

export async function getDownloadUrl(datasetId: number): Promise<string> {
  const result = await apiJson<{ url: string }>(`${API_BASE}/datasets/${datasetId}/download-url`)
  return result.url
}
