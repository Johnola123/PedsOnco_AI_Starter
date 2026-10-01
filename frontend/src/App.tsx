import { FormEvent, useEffect, useState } from 'react'
import { Dataset, getDatasets, getHealth, Health, uploadDataset } from './api'

function formatBytes(bytes: number) {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [projectName, setProjectName] = useState('Demo Project')
  const [file, setFile] = useState<File | null>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  async function refresh() {
    const [h, d] = await Promise.all([getHealth(), getDatasets()])
    setHealth(h)
    setDatasets(d)
  }

  useEffect(() => {
    refresh().catch((error) => setMessage(String(error)))
  }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!file) {
      setMessage('Choose a file first.')
      return
    }
    setBusy(true)
    setMessage('Uploading...')
    try {
      await uploadDataset(file, projectName)
      setMessage('Dataset registered successfully.')
      setFile(null)
      const input = document.getElementById('dataset-file') as HTMLInputElement | null
      if (input) input.value = ''
      await refresh()
    } catch (error) {
      setMessage(String(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">PedsOnco AI</div>
        <nav>
          <a className="active" href="#dashboard">Dashboard</a>
          <a href="#upload">Add Data</a>
          <a href="#datasets">Datasets</a>
          <a className="disabled" aria-disabled="true">Harmonize · next</a>
          <a className="disabled" aria-disabled="true">QC · next</a>
          <a className="disabled" aria-disabled="true">Cohorts · next</a>
        </nav>
      </aside>

      <main>
        <header>
          <div>
            <p className="eyebrow">Research data platform · starter build</p>
            <h1>Data ingestion foundation</h1>
            <p className="subtext">React + FastAPI + PostgreSQL + MinIO/S3 behind Nginx.</p>
          </div>
          <div className={`status ${health?.status === 'ok' ? 'good' : ''}`}>
            {health?.status === 'ok' ? 'Stack healthy' : 'Checking services'}
          </div>
        </header>

        <section id="dashboard" className="metrics">
          <article><span>Datasets</span><strong>{datasets.length}</strong></article>
          <article><span>Database</span><strong>{health?.database ?? '—'}</strong></article>
          <article><span>Object storage</span><strong>{health?.object_storage ?? '—'}</strong></article>
        </section>

        <section id="upload" className="panel">
          <div className="panel-title">
            <div><p className="eyebrow">Step 1</p><h2>Register a dataset</h2></div>
            <span>CSV · JSON · VCF · FASTQ metadata · any file</span>
          </div>
          <form onSubmit={submit}>
            <label>
              Project name
              <input value={projectName} onChange={(e) => setProjectName(e.target.value)} />
            </label>
            <label>
              File
              <input id="dataset-file" type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>
            <button disabled={busy} type="submit">{busy ? 'Uploading…' : 'Upload and register'}</button>
          </form>
          {message && <p className="message">{message}</p>}
        </section>

        <section id="datasets" className="panel">
          <div className="panel-title"><div><p className="eyebrow">Data registry</p><h2>Recent datasets</h2></div></div>
          {datasets.length === 0 ? (
            <p className="empty">No files registered yet. Upload a small test file above.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>File</th><th>Project</th><th>Size</th><th>Status</th><th>SHA-256</th></tr></thead>
                <tbody>
                  {datasets.map((dataset) => (
                    <tr key={dataset.id}>
                      <td>{dataset.original_name}</td>
                      <td>{dataset.project_name}</td>
                      <td>{formatBytes(dataset.size_bytes)}</td>
                      <td><span className="pill">{dataset.status}</span></td>
                      <td className="hash">{dataset.sha256.slice(0, 14)}…</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
