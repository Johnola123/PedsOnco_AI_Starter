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

export type Cohort = {
  name: string
  kind: 'source' | 'merged'
  file_count: number
  size_bytes: number
  formats: string[]
  source_cohorts: string[]
}

export type DatasetProfile = {
  dataset_id: number
  format_name: string
  table_count: number
  profile: {
    format: string
    filename: string
    table_count: number
    message?: string
    sheets?: Array<{
      name: string
      rows: number
      columns: number
      role: string
      empty: boolean
      preview?: unknown[][]
      fields?: Array<{ name: string; inferred_type: string; sample_values: string[] }>
    }>
    tables?: Array<{
      name: string
      rows: number
      columns: number
      role: string
      preview?: unknown[][]
      fields?: Array<{ name: string; inferred_type: string; sample_values: string[] }>
    }>
    paths?: string[]
    records?: number
  }
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

export async function getCohorts(): Promise<Cohort[]> {
  return apiJson(`${API_BASE}/cohorts`)
}

export async function getCohortDatasets(name: string): Promise<Dataset[]> {
  return apiJson(`${API_BASE}/cohorts/${encodeURIComponent(name)}/datasets`)
}

export async function getDatasetProfile(datasetId: number): Promise<DatasetProfile> {
  return apiJson(`${API_BASE}/datasets/${datasetId}/profile`)
}

export async function mergeCohorts(name: string, sourceCohorts: string[], notes?: string): Promise<void> {
  await apiJson(`${API_BASE}/cohorts/merge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, source_cohorts: sourceCohorts, notes: notes || null }),
  })
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
      if (event.lengthComputable && onProgress) onProgress(Math.round((event.loaded / event.total) * 100))
    }
    xhr.onerror = () => reject(new Error('Direct upload failed. Check MinIO/S3 reachability and CORS.'))
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve()
      else reject(new Error(`Object-storage upload failed (${xhr.status}).`))
    }
    xhr.send(file)
  })
}

export async function completeDirectUpload(file: File, projectName: string, objectKey: string): Promise<Dataset> {
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


export type WorkspaceRecord = {
  id: number
  project_name: string
  record_type: string
  name: string
  payload: Record<string, unknown>
  created_at: string
}

export async function getWorkspaceRecords(cohortName: string, recordType?: string): Promise<WorkspaceRecord[]> {
  const query = recordType ? `?record_type=${encodeURIComponent(recordType)}` : ''
  return apiJson(`${API_BASE}/cohorts/${encodeURIComponent(cohortName)}/workspace-records${query}`)
}

export async function createWorkspaceRecord(
  cohortName: string,
  recordType: string,
  name: string,
  payload: Record<string, unknown>,
): Promise<WorkspaceRecord> {
  return apiJson(`${API_BASE}/cohorts/${encodeURIComponent(cohortName)}/workspace-records`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ record_type: recordType, name, payload }),
  })
}

export async function deleteWorkspaceRecord(cohortName: string, recordId: number): Promise<void> {
  await apiJson(`${API_BASE}/cohorts/${encodeURIComponent(cohortName)}/workspace-records/${recordId}`, { method: 'DELETE' })
}

export async function getCohortExportManifest(cohortName: string): Promise<Record<string, unknown>> {
  return apiJson(`${API_BASE}/cohorts/${encodeURIComponent(cohortName)}/export-manifest`)
}


export type MappingValidationItem = {
  source: string
  canonical: string
  confidence: number
  status: 'accept' | 'review' | 'reject'
}

export type ValidationIssue = {
  level: 'error' | 'warning' | string
  code: string
  field?: string | null
  message: string
}

export type HarmonizationValidation = {
  valid: boolean
  dataset_id: number
  dataset_name: string
  table_name?: string | null
  score: number
  accepted_count: number
  review_count: number
  rejected_count: number
  issues: ValidationIssue[]
}

export type IntegrationValidation = {
  valid: boolean
  left_dataset_name: string
  right_dataset_name: string
  issues: ValidationIssue[]
}

export async function validateHarmonization(params: {
  datasetId: number
  tableName?: string | null
  mappings: MappingValidationItem[]
}): Promise<HarmonizationValidation> {
  return apiJson(`${API_BASE}/harmonization/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id: params.datasetId, table_name: params.tableName || null, mappings: params.mappings }),
  })
}

export async function validateIntegration(params: {
  leftDatasetId: number
  leftKey: string
  rightDatasetId: number
  rightKey: string
  relationship: string
}): Promise<IntegrationValidation> {
  return apiJson(`${API_BASE}/integration/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      left_dataset_id: params.leftDatasetId, left_key: params.leftKey,
      right_dataset_id: params.rightDatasetId, right_key: params.rightKey, relationship: params.relationship,
    }),
  })
}
