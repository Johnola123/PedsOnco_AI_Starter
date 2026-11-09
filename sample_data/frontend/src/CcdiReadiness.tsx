import { useState } from 'react'

type Sheet = { name: string; header_row: number | null; fields: Array<{ name: string }>; nonempty_rows: number }
type Issue = { level: string; code: string; sheet?: string; message: string }
type Inspection = { status: string; sheets: Sheet[]; issues: Issue[]; summary: { error_count: number; warning_count: number }; template_sha256: string }
const api = import.meta.env.VITE_API_BASE_URL || '/api'

async function postFile(path: string, field: string, file: File): Promise<Inspection> {
  const body = new FormData(); body.append(field, file)
  const response = await fetch(`${api}${path}`, { method: 'POST', body })
  if (!response.ok) { const e = await response.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${response.status}`) }
  return response.json()
}
export default function CcdiReadiness() {
  const [template, setTemplate] = useState<File | null>(null)
  const [source, setSource] = useState<File | null>(null)
  const [inspection, setInspection] = useState<Inspection | null>(null)
  const [check, setCheck] = useState<Inspection | null>(null)
  const [node, setNode] = useState('participant')
  const [mapping, setMapping] = useState('{\n  "patient_id": "participant_id"\n}')
  const [accession, setAccession] = useState('')
  const [sourceLookup, setSourceLookup] = useState('TARGET-NBL')
  const [sourceType, setSourceType] = useState<'gdc' | 'geo'>('gdc')
  const [sourceInfo, setSourceInfo] = useState('')
  const [sourceLink, setSourceLink] = useState('')
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)
  const selectedSheet = inspection?.sheets.find(s => s.name.toLowerCase() === node.toLowerCase())
  async function lookupSource() {
    setRunning(true); setError(''); setSourceInfo(''); setSourceLink('')
    const path = sourceType === 'gdc' ? `/public-sources/gdc/project/${encodeURIComponent(sourceLookup)}` : `/public-sources/geo/study/${encodeURIComponent(sourceLookup)}`
    try {
      const response = await fetch(`${api}${path}`)
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`)
      setSourceLink(typeof result.link === 'string' ? result.link : '')
      setAccession(sourceLookup)
      setSourceInfo(sourceType === 'geo' ? `GEO ${result.accession}: ${result.result_count} matching metadata record(s). This verifies accession discovery only; it does not import study files.` : `GDC ${result.project_id}: public project metadata retrieved. This does not download clinical, molecular, or imaging files.`)
    } catch(e) { setError(String(e)) } finally { setRunning(false) }
  }
  async function inspect() {
    if (!template) return
    setRunning(true); setError(''); setInspection(null)
    try { const result = await postFile('/ccdi/inspect-template', 'template', template); setInspection(result); if (result.sheets.length) setNode(result.sheets.find(s => s.name === 'participant')?.name || result.sheets[0].name) }
    catch (e) { setError(String(e)) } finally { setRunning(false) }
  }
  async function validateWorkbook(file: File) {
    setRunning(true); setError(''); setCheck(null)
    try { setCheck(await postFile('/ccdi/validate-workbook', 'workbook', file)) }
    catch (e) { setError(String(e)) } finally { setRunning(false) }
  }
  async function build() {
    if (!template || !source) return
    setRunning(true); setError('')
    try {
      const parsed = JSON.parse(mapping)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('Use a JSON mapping object.')
      const body = new FormData(); body.append('template', template); body.append('source', source)
      body.append('node', node); body.append('mappings_json', JSON.stringify(parsed)); body.append('accession', accession)
      const response = await fetch(`${api}/ccdi/build-candidate`, { method: 'POST', body })
      if (!response.ok) { const e = await response.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${response.status}`) }
      const blob = await response.blob(); const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = 'ccdi_candidate_package.zip'; a.click()
      setTimeout(() => URL.revokeObjectURL(url), 1500)
    } catch (e) { setError(String(e)) } finally { setRunning(false) }
  }
  return <section className="panel" style={{maxWidth:960}}>
    <p className="eyebrow">Track 1 · Metadata evidence workspace</p>
    <h1>CCDI submission-readiness checks</h1>
    <p>Supply the official CCDI metadata template to inspect node properties. Build a <strong>candidate</strong> workbook from a public CSV/TSV file. This is preliminary structural QC, <strong>not CCDI certification</strong>, ontology validation, or an authorized data submission.</p>
    <p><a href="https://github.com/CBIIT/ccdi-dcc-model" target="_blank" rel="noreferrer">Get current CCDI data model / metadata template ↗</a></p>
    <h2>Public source discovery (live web)</h2>
    <div className="two"><label className="field"><span>Repository</span><select value={sourceType} onChange={e => { const value = e.target.value as 'gdc' | 'geo'; setSourceType(value); setSourceLookup(value === 'gdc' ? 'TARGET-NBL' : 'GSE12345') }}><option value="gdc">GDC project</option><option value="geo">GEO study</option></select></label><label className="field"><span>Accession</span><input value={sourceLookup} onChange={e => setSourceLookup(e.target.value)} /></label></div>
    <button className="secondary" disabled={running || !sourceLookup} onClick={lookupSource}>Verify public accession</button>
    {sourceInfo && <div role="status" style={{padding:12,border:'1px solid #cbd5e1',borderRadius:8}}><p>{sourceInfo}</p>{sourceLink && <p><a href={sourceLink} target="_blank" rel="noreferrer">Open study at source repository ↗</a></p>}<p><strong>Next:</strong> select an authorized public CSV/TSV metadata table from the repository (or your local cohort), upload the current official CCDI .xlsx template below, inspect its target properties, then upload the source table and review the mapping JSON to export a candidate package.</p><small>Automatic study-file selection and accession-to-cohort ingestion are planned enhancements, not implemented here.</small></div>}
    <hr />
    <div className="field"><span>1. Upload official CCDI .xlsx template</span><input type="file" accept=".xlsx" onChange={e => setTemplate(e.target.files?.[0] || null)} /></div>
    <button className="primary" disabled={!template || running} onClick={inspect}>Inspect official template</button>
    {inspection && <div style={{marginTop:20}}><h2>Template inspection</h2><p>State: {inspection.status} · {inspection.sheets.length} node sheets · {inspection.summary.error_count} errors · {inspection.summary.warning_count} warnings</p><p><small>SHA256: {inspection.template_sha256}</small></p><label className="field"><span>CCDI target node</span><select value={node} onChange={e => setNode(e.target.value)}>{inspection.sheets.map(s => <option key={s.name} value={s.name}>{s.name}</option>)}</select></label>
      <p>Detected header row: {selectedSheet?.header_row || 'unknown'}. Properties: {selectedSheet?.fields.map(f => f.name).join(', ') || '(none detected)'}</p>
      {inspection.issues.length > 0 && <details><summary>Validation warnings and errors</summary><ul>{inspection.issues.map((i,j) => <li key={j}>{i.level}: {i.code} ({i.sheet || 'workbook'}) — {i.message}</li>)}</ul></details>}
    </div>}
    <hr />
    <h2>2. Convert a public cohort CSV/TSV to a candidate CCDI node</h2>
    <p>Use a small, de-identified source table. Mappings must use source header names and target properties shown above. Review every mapping manually; no AI mapping is claimed here.</p>
    <label className="field"><span>Public source table (.csv or .tsv)</span><input type="file" accept=".csv,.tsv" onChange={e => setSource(e.target.files?.[0] || null)} /></label>
    <label className="field"><span>Study accession / provenance</span><input value={accession} onChange={e => setAccession(e.target.value)} placeholder="e.g. GEO or GDC accession" /></label>
    <label className="field"><span>Reviewed mappings (JSON)</span><textarea rows={6} value={mapping} onChange={e => setMapping(e.target.value)} /></label>
    <button className="primary" disabled={!template || !source || !inspection || running || inspection.summary.error_count > 0} onClick={build}>Export candidate ZIP + QC + provenance</button>
    <hr />
    <h2>3. Validate an edited/populated metadata workbook</h2>
    <label className="field"><span>CCDI metadata .xlsx</span><input type="file" accept=".xlsx" onChange={e => { if (e.target.files?.[0]) void validateWorkbook(e.target.files[0]) }} /></label>
    {check && <div><p>Result: {check.status} — {check.summary.error_count} structural errors, {check.summary.warning_count} warnings.</p><ul>{check.issues.map((i,j) => <li key={j}>{i.sheet}: {i.message}</li>)}</ul></div>}
    {error && <p role="alert" style={{color:'#b42318'}}>{error}</p>}
    <p><small>Controlled-access dbGaP registration, CCDI curation, validated vocabulary terms, imaging risk assessment, institutional consent and authorized S3 uploads remain outside this local prototype.</small></p>
  </section>
}
