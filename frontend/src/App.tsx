import { DragEvent, FormEvent, useEffect, useMemo, useState } from 'react'
import {
  Dataset,
  getDatasets,
  getDownloadUrl,
  getHealth,
  Health,
  importExternalUrl,
  uploadFileDirect,
} from './api'

const TYPE_INFO: Record<string, { label: string; tone: string }> = {
  csv: { label: 'Clinical CSV', tone: 'blue' }, tsv: { label: 'TSV', tone: 'blue' }, xlsx: { label: 'Excel', tone: 'blue' },
  json: { label: 'JSON', tone: 'violet' }, ndjson: { label: 'NDJSON', tone: 'violet' },
  fa: { label: 'FASTA', tone: 'green' }, fasta: { label: 'FASTA', tone: 'green' }, fq: { label: 'FASTQ', tone: 'green' }, fastq: { label: 'FASTQ', tone: 'green' },
  vcf: { label: 'VCF', tone: 'amber' }, maf: { label: 'MAF', tone: 'amber' }, bam: { label: 'BAM', tone: 'amber' }, cram: { label: 'CRAM', tone: 'amber' },
  png: { label: 'Image', tone: 'pink' }, jpg: { label: 'Image', tone: 'pink' }, jpeg: { label: 'Image', tone: 'pink' }, dcm: { label: 'DICOM', tone: 'pink' },
  parquet: { label: 'Parquet', tone: 'cyan' }, txt: { label: 'Text', tone: 'slate' }, zip: { label: 'Archive', tone: 'slate' },
}

const SUPPORTED_GROUPS = [
  { title: 'Clinical & metadata', icon: '▦', formats: 'CSV · TSV · XLSX · JSON · NDJSON', text: 'Participants, diagnoses, treatment, outcomes, sample manifests and data dictionaries.' },
  { title: 'Sequence & genomics', icon: '⌁', formats: 'FASTA · FASTQ · VCF · MAF · BAM · CRAM', text: 'Reference/target sequences, raw reads, variants, alignments and assay outputs.' },
  { title: 'Imaging & pathology', icon: '◫', formats: 'PNG · JPG · DICOM · WSI metadata', text: 'Preview images and imaging manifests now; large image objects live in MinIO/S3.' },
  { title: 'Analysis-ready matrices', icon: '⌗', formats: 'TSV · CSV · Parquet', text: 'RNA expression, proteomics, methylation, features and derived analysis tables.' },
]

function formatBytes(bytes: number) {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

function extension(name: string) {
  const clean = name.toLowerCase().replace(/\.gz$/, '')
  return clean.split('.').pop() || 'file'
}

function typeInfo(name: string) {
  return TYPE_INFO[extension(name)] || { label: extension(name).toUpperCase(), tone: 'slate' }
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [projectName, setProjectName] = useState('Demo Cohort')
  const [files, setFiles] = useState<File[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [intakeMode, setIntakeMode] = useState<'files' | 'url'>('files')
  const [progress, setProgress] = useState<Record<string, number>>({})
  const [externalUrl, setExternalUrl] = useState('')
  const [externalFilename, setExternalFilename] = useState('')
  const [bearerToken, setBearerToken] = useState('')

  async function refresh() {
    const [h, d] = await Promise.all([getHealth(), getDatasets()])
    setHealth(h)
    setDatasets(d)
  }

  useEffect(() => { refresh().catch((error) => setMessage(String(error))) }, [])

  function addFiles(incoming: FileList | File[]) {
    const next = Array.from(incoming)
    setFiles((current) => {
      const map = new Map(current.map((item) => [`${item.name}:${item.size}`, item]))
      next.forEach((item) => map.set(`${item.name}:${item.size}`, item))
      return Array.from(map.values())
    })
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault(); setDragging(false); addFiles(event.dataTransfer.files)
  }

  async function submitFiles(event: FormEvent) {
    event.preventDefault()
    if (files.length === 0) { setMessage('Choose one or more files first.'); return }
    setBusy(true); setProgress({})
    try {
      for (let i = 0; i < files.length; i += 1) {
        const file = files[i]
        setMessage(`Preparing direct upload ${i + 1} of ${files.length}: ${file.name}`)
        await uploadFileDirect(file, projectName, (pct) => setProgress((p) => ({ ...p, [`${file.name}:${file.size}`]: pct })))
      }
      setMessage(`${files.length} file${files.length === 1 ? '' : 's'} uploaded directly to object storage and registered.`)
      setFiles([]); setProgress({})
      const input = document.getElementById('dataset-file') as HTMLInputElement | null
      if (input) input.value = ''
      await refresh()
    } catch (error) { setMessage(error instanceof Error ? error.message : String(error)) }
    finally { setBusy(false) }
  }

  async function submitUrl(event: FormEvent) {
    event.preventDefault()
    if (!externalUrl.trim()) { setMessage('Enter an external HTTP(S) URL or API endpoint.'); return }
    setBusy(true)
    try {
      setMessage('Importing external URL/API response into object storage…')
      const result = await importExternalUrl({ projectName, url: externalUrl.trim(), filename: externalFilename.trim() || undefined, bearerToken: bearerToken.trim() || undefined })
      setMessage(`Imported ${result.original_name} successfully.`)
      setExternalUrl(''); setExternalFilename(''); setBearerToken('')
      await refresh()
    } catch (error) { setMessage(error instanceof Error ? error.message : String(error)) }
    finally { setBusy(false) }
  }

  async function download(dataset: Dataset) {
    try {
      const url = await getDownloadUrl(dataset.id)
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch (error) { setMessage(error instanceof Error ? error.message : String(error)) }
  }

  const projects = useMemo(() => new Set(datasets.map((d) => d.project_name)).size, [datasets])
  const totalBytes = useMemo(() => datasets.reduce((sum, d) => sum + d.size_bytes, 0), [datasets])
  const types = useMemo(() => Array.from(new Set(datasets.map((d) => extension(d.original_name)))).sort(), [datasets])
  const filtered = useMemo(() => datasets.filter((dataset) => {
    const matchesText = `${dataset.original_name} ${dataset.project_name}`.toLowerCase().includes(query.toLowerCase())
    return matchesText && (typeFilter === 'all' || extension(dataset.original_name) === typeFilter)
  }), [datasets, query, typeFilter])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-wrap"><div className="brand-mark">P</div><div><div className="brand">PedsOnco AI</div><small>Research workspace</small></div></div>
        <nav><a className="active" href="#dashboard">Overview</a><a href="#upload">Add data</a><a href="#datasets">Data registry</a><a href="#formats">File types</a><a className="disabled" aria-disabled="true">Harmonize <b>soon</b></a><a className="disabled" aria-disabled="true">Cohorts <b>soon</b></a></nav>
        <div className="sidebar-note">Browser-direct object storage uploads + external URL/API ingestion.</div>
      </aside>

      <main>
        <header className="hero" id="dashboard">
          <div><p className="eyebrow">Multimodal pediatric oncology data platform</p><h1>Bring each cohort's data together.</h1><p className="subtext">Upload large files directly to MinIO/S3, import public or bearer-protected URLs/APIs, and keep metadata in PostgreSQL.</p><div className="hero-actions"><a className="primary-link" href="#upload">Add cohort data</a><a className="secondary-link" href="#datasets">Browse registry</a></div></div>
          <div className={`status ${health?.status === 'ok' ? 'good' : ''}`}><span className="status-dot" />{health?.status === 'ok' ? 'Stack healthy' : 'Checking services'}</div>
        </header>

        <section className="metrics" aria-label="Platform summary">
          <article><div className="metric-icon blue">▦</div><div><span>Registered files</span><strong>{datasets.length}</strong></div></article>
          <article><div className="metric-icon violet">◇</div><div><span>Cohorts / projects</span><strong>{projects}</strong></div></article>
          <article><div className="metric-icon green">↟</div><div><span>Stored data</span><strong>{formatBytes(totalBytes)}</strong></div></article>
          <article><div className="metric-icon amber">●</div><div><span>Object storage</span><strong>{health?.object_storage ?? '—'}</strong></div></article>
        </section>

        <section id="upload" className="panel upload-panel">
          <div className="panel-title"><div><p className="eyebrow">Data intake</p><h2>Add data to a cohort</h2><p className="section-copy">Choose direct browser upload or import from an external HTTP(S) URL/API.</p></div><span className="mini-badge">Presigned S3 ready</span></div>
          <div className="mode-tabs" role="tablist" aria-label="Data intake mode">
            <button type="button" className={intakeMode === 'files' ? 'active' : ''} onClick={() => setIntakeMode('files')}>Computer / device</button>
            <button type="button" className={intakeMode === 'url' ? 'active' : ''} onClick={() => setIntakeMode('url')}>External URL / API</button>
          </div>

          {intakeMode === 'files' ? (
            <form onSubmit={submitFiles}>
              <label className="field"><span>Cohort / project name</span><input value={projectName} onChange={(e) => setProjectName(e.target.value)} placeholder="e.g. Neuroblastoma Pilot" /></label>
              <div className={`dropzone ${dragging ? 'dragging' : ''}`} onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
                <div className="drop-icon">⇧</div><div><strong>Drop cohort files here</strong><p>Files go directly from the browser to MinIO/S3 after FastAPI signs the request.</p></div>
                <label className="choose-button" htmlFor="dataset-file">Browse files</label><input id="dataset-file" className="visually-hidden" type="file" multiple onChange={(e) => e.target.files && addFiles(e.target.files)} />
              </div>
              {files.length > 0 && <div className="selected-files"><div className="selected-heading"><strong>{files.length} file{files.length === 1 ? '' : 's'} selected</strong><button type="button" className="text-button" onClick={() => setFiles([])}>Clear</button></div><div className="file-chips">{files.map((item) => { const info = typeInfo(item.name); const key = `${item.name}:${item.size}`; return <span className={`file-chip ${info.tone}`} key={key}><b>{info.label}</b>{item.name}<em>{progress[key] !== undefined ? `${progress[key]}%` : formatBytes(item.size)}</em><button type="button" aria-label={`Remove ${item.name}`} onClick={() => setFiles((current) => current.filter((f) => f !== item))}>×</button></span> })}</div></div>}
              <div className="upload-actions"><button className="primary-button" disabled={busy} type="submit">{busy ? 'Uploading…' : `Upload ${files.length || ''} file${files.length === 1 ? '' : 's'}`}</button><span>FastAPI signs → browser PUTs to MinIO/S3 → FastAPI verifies and registers.</span></div>
            </form>
          ) : (
            <form onSubmit={submitUrl} className="url-form">
              <label className="field"><span>Cohort / project name</span><input value={projectName} onChange={(e) => setProjectName(e.target.value)} /></label>
              <label className="field full"><span>External URL or GET API endpoint</span><input type="url" value={externalUrl} onChange={(e) => setExternalUrl(e.target.value)} placeholder="https://example.org/data/cohort.json" required /></label>
              <label className="field"><span>Optional filename override</span><input value={externalFilename} onChange={(e) => setExternalFilename(e.target.value)} placeholder="cohort.json" /></label>
              <label className="field"><span>Optional bearer token</span><input type="password" value={bearerToken} onChange={(e) => setBearerToken(e.target.value)} autoComplete="off" placeholder="Used once; never stored" /></label>
              <div className="security-note"><strong>URL import safety</strong><span>Only HTTP(S) is accepted. Local/private-network destinations are blocked. Bearer tokens are used transiently and are not stored.</span></div>
              <div className="upload-actions"><button className="primary-button" disabled={busy} type="submit">{busy ? 'Importing…' : 'Import URL / API'}</button><span>Best for public downloads or GET APIs that return a file/JSON payload.</span></div>
            </form>
          )}
          {message && <p className="message" role="status">{message}</p>}
        </section>

        <section className="workflow-strip" aria-label="Direct upload architecture">
          <div><b>1</b><span>Browser requests upload URL</span></div><i>→</i><div><b>2</b><span>FastAPI signs object key</span></div><i>→</i><div><b>3</b><span>Browser PUTs to MinIO/S3</span></div><i>→</i><div><b>4</b><span>FastAPI verifies + registers</span></div>
        </section>

        <section id="formats" className="panel"><div className="panel-title"><div><p className="eyebrow">Flexible ingestion</p><h2>Useful file types by cohort</h2><p className="section-copy">A cohort can contain several modalities linked by participant, specimen and assay identifiers.</p></div></div><div className="format-grid">{SUPPORTED_GROUPS.map((group) => <article className="format-card" key={group.title}><div className="format-icon">{group.icon}</div><h3>{group.title}</h3><strong>{group.formats}</strong><p>{group.text}</p></article>)}</div></section>

        <section id="datasets" className="panel">
          <div className="panel-title"><div><p className="eyebrow">Data registry</p><h2>Registered cohort files</h2><p className="section-copy">Search, filter, and generate short-lived download links.</p></div></div>
          <div className="registry-tools"><label className="search-box"><span>⌕</span><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search files or cohorts…" /></label><select aria-label="Filter by file type" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}><option value="all">All file types</option>{types.map((type) => <option value={type} key={type}>{type.toUpperCase()}</option>)}</select><button type="button" className="refresh-button" onClick={() => refresh().catch((error) => setMessage(String(error)))}>Refresh</button></div>
          {filtered.length === 0 ? <div className="empty-state"><div>◎</div><strong>{datasets.length === 0 ? 'No files registered yet' : 'No files match your filters'}</strong><p>{datasets.length === 0 ? 'Upload local files or import a URL/API to populate this registry.' : 'Try a different search term or file type.'}</p></div> : <>
            <div className="dataset-cards">{filtered.map((dataset) => { const info = typeInfo(dataset.original_name); return <article className="dataset-card" key={`card-${dataset.id}`}><div className={`type-icon ${info.tone}`}>{extension(dataset.original_name).slice(0, 4).toUpperCase()}</div><div className="dataset-card-body"><strong title={dataset.original_name}>{dataset.original_name}</strong><span>{dataset.project_name}</span><small>{formatBytes(dataset.size_bytes)} · {info.label}</small></div><button type="button" className="download-button" onClick={() => download(dataset)}>Download</button></article> })}</div>
            <div className="table-wrap"><table><thead><tr><th>File</th><th>Cohort / project</th><th>Type</th><th>Size</th><th>Status</th><th>SHA-256</th><th /></tr></thead><tbody>{filtered.map((dataset) => { const info = typeInfo(dataset.original_name); return <tr key={dataset.id}><td className="file-name">{dataset.original_name}</td><td>{dataset.project_name}</td><td><span className={`type-pill ${info.tone}`}>{info.label}</span></td><td>{formatBytes(dataset.size_bytes)}</td><td><span className="pill">{dataset.status}</span></td><td className="hash">{dataset.sha256.slice(0, 14)}…</td><td><button type="button" className="text-button" onClick={() => download(dataset)}>Download</button></td></tr> })}</tbody></table></div>
          </>}
        </section>

        <footer><strong>PedsOnco AI</strong><span>Research use only · no clinical decision support</span></footer>
      </main>
    </div>
  )
}
