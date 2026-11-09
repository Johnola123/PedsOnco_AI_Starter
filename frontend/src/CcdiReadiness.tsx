import './ccdi-studio.css'
import { useMemo, useState } from 'react'

type Sheet = { name: string; header_row: number | null; fields: Array<{ name: string; required?: boolean; relationship?: boolean; datatype?: string; allowed_count?: number }>; nonempty_rows: number; mandatory_columns?: string[] }
type Issue = { level: string; code: string; sheet?: string; message: string }
type Inspection = { status: string; sheets: Sheet[]; issues: Issue[]; summary: { error_count: number; warning_count: number }; template_sha256: string; dictionary_property_count?: number; value_set_count?: number }
type MapEntry = { source: string; target: string }
const api = import.meta.env.VITE_API_BASE_URL || '/api'
const CCDI_MODEL = 'https://github.com/CBIIT/ccdi-dcc-model'
const CCDI_HELP = 'NCIChildhoodCancerDataInitiative@mail.nih.gov'
const steps = ['Discover','Select files','Inspect template','Map & export','Validate','Complete']

async function postFile(path: string, field: string, file: File): Promise<Inspection> {
  const body = new FormData(); body.append(field, file)
  const response = await fetch(`${api}${path}`, { method: 'POST', body })
  if (!response.ok) { const e = await response.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${response.status}`) }
  return response.json()
}
function saveText(filename: string, content: string, type = 'text/plain') {
  const blob = new Blob([content], {type}); const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 2000)
}
function parseDelimitedHeader(line: string, sep: string) {
  // Header-only parser. Quoted commas/tabs are supported; no content is sent to an AI service.
  const parts: string[] = []; let token = ''; let quoted = false
  for (let i = 0; i < line.length; i++) {
    const c = line[i]
    if (c === '"' && quoted && line[i + 1] === '"') { token += '"'; i++; continue }
    if (c === '"') { quoted = !quoted; continue }
    if (c === sep && !quoted) { parts.push(token.trim()); token = ''; continue }
    token += c
  }
  parts.push(token.trim()); return parts.filter(Boolean)
}

export default function CcdiReadiness() {
  const [template, setTemplate] = useState<File | null>(null)
  const [multiZip, setMultiZip] = useState<File | null>(null)
  const [multiJson, setMultiJson] = useState('')
  const [multiExported, setMultiExported] = useState(false)
  const [source, setSource] = useState<File | null>(null)
  const [inspection, setInspection] = useState<Inspection | null>(null)
  const [check, setCheck] = useState<Inspection | null>(null)
  const [node, setNode] = useState('participant')
  const [rows, setRows] = useState<MapEntry[]>([])
  const [sourceHeaders, setSourceHeaders] = useState<string[]>([])
  const [manualMapping, setManualMapping] = useState('')
  const [advanced, setAdvanced] = useState(false)
  const [accession, setAccession] = useState('')
  const [sourceLookup, setSourceLookup] = useState('TARGET-NBL')
  const [sourceType, setSourceType] = useState<'gdc' | 'geo'>('gdc')
  const [sourceInfo, setSourceInfo] = useState('')
  const [sourceLink, setSourceLink] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [running, setRunning] = useState(false)
  const [exported, setExported] = useState(false)
  const [agreed, setAgreed] = useState(false)
  const [complete, setComplete] = useState(false)
  const [activeStep, setActiveStep] = useState(0)
  const selectedSheet = inspection?.sheets.find(s => s.name.toLowerCase() === node.toLowerCase())
  const properties = useMemo(() => selectedSheet?.fields.map(f => f.name) || [], [selectedSheet])
  const mapping = useMemo(() => Object.fromEntries(rows.filter(r => r.source && r.target).map(r => [r.source, r.target])), [rows])
  const duplicateTargets = useMemo(() => rows.filter(r => r.target).map(r => r.target).filter((v,i,a) => a.indexOf(v) !== i), [rows])
  const counted = [Boolean(sourceInfo), Boolean(source), Boolean(inspection && inspection.summary.error_count === 0), exported, Boolean(check && check.summary.error_count === 0), complete]
  const progress = Math.round((counted.filter(Boolean).length / counted.length) * 100)
  const canComplete = exported && Boolean(check && check.summary.error_count === 0) && agreed

  async function lookupSource() {
    setRunning(true); setError(''); setSourceInfo(''); setSourceLink(''); setComplete(false)
    const path = sourceType === 'gdc' ? `/public-sources/gdc/project/${encodeURIComponent(sourceLookup.trim())}` : `/public-sources/geo/study/${encodeURIComponent(sourceLookup.trim())}`
    try {
      const response = await fetch(`${api}${path}`); const result = await response.json()
      if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`)
      setSourceLink(typeof result.link === 'string' ? result.link : '')
      setAccession(sourceLookup.trim())
      setSourceInfo(sourceType === 'geo' ? `GEO ${result.accession}: ${result.result_count} public metadata record(s) found.` : `GDC ${result.project_id}: project metadata discovered.`)
      setActiveStep(1); setNotice('Accession verified. Select an allowed public CSV/TSV table from the linked repository. This lookup does not download files.')
    } catch(e) { setError(String(e)) } finally { setRunning(false) }
  }
  async function selectSource(file: File | null) {
    setSource(file); setRows([]); setExported(false); setCheck(null); setComplete(false); setSourceHeaders([])
    if (!file) return
    if (!/\.(csv|tsv)$/i.test(file.name)) { setError('Choose a CSV or TSV source table.'); return }
    try {
      const preview = await file.slice(0, 128 * 1024).text()
      const firstLine = preview.split(/\r?\n/)[0].replace(/^\ufeff/, '')
      const headers = parseDelimitedHeader(firstLine, file.name.toLowerCase().endsWith('.tsv') ? '\t' : ',')
      setSourceHeaders(headers)
      setRows(headers.map(h => ({source:h,target:''})))
      setActiveStep(2)
      setNotice(`${headers.length} source headers detected. Candidate export currently supports at most 10 MiB / 5,000 source rows.`)
    } catch(e) { setError(`Could not inspect source header: ${String(e)}`) }
  }
  async function useBundledTemplate() {
    setRunning(true); setError('')
    try {
      const response = await fetch(`${api}/ccdi/reference-template`)
      if (!response.ok) throw new Error(`Reference template download failed: ${response.status}`)
      const file = new File([await response.blob()], 'CCDI-DCC_Submission_Template_v2.2.0.xlsx', {type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
      setTemplate(file); setInspection(null); setCheck(null); setExported(false); setComplete(false)
      setNotice('Official v2.2.0 template loaded from the application. Inspect it to continue.')
    } catch(e) { setError(String(e)) } finally { setRunning(false) }
  }
  async function inspect() {
    if (!template) return
    setRunning(true); setError(''); setInspection(null); setComplete(false)
    try {
      const result = await postFile('/ccdi/inspect-template', 'template', template); setInspection(result)
      if (result.sheets.length) setNode(result.sheets.find(s => s.name.toLowerCase() === 'participant')?.name || result.sheets[0].name)
      setActiveStep(3); setNotice(`Template inspected: ${result.sheets.length} data-model nodes, ${result.dictionary_property_count ?? 0} dictionary properties, ${result.value_set_count ?? 0} value sets.`)
    } catch (e) { setError(String(e)) } finally { setRunning(false) }
  }
  async function buildMulti() {
    if (!template || !multiZip || !multiJson.trim()) return
    setRunning(true); setError(''); setMultiExported(false); setComplete(false)
    try {
      const cfg = JSON.parse(multiJson)
      if (!cfg || typeof cfg !== 'object' || Array.isArray(cfg)) throw new Error('Mapping configuration must be an object keyed by CCDI node')
      const body = new FormData()
      body.append('template', template); body.append('sources', multiZip)
      body.append('configuration_json', JSON.stringify(cfg)); body.append('accession', accession)
      const res = await fetch(`${api}/ccdi/build-multi-candidate`, {method:'POST', body})
      if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail || `HTTP ${res.status}`) }
      const blob = await res.blob(); const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = 'ccdi_multinode_candidate.zip'; a.click()
      setTimeout(()=>URL.revokeObjectURL(url), 2000)
      setMultiExported(true); setExported(true); setActiveStep(4)
      setNotice('Multi-sheet candidate created. Extract the Excel workbook and validate it below before local completion.')
    } catch(e) { setError(String(e)) } finally { setRunning(false) }
  }
  async function validateWorkbook(file: File) {
    setRunning(true); setError(''); setCheck(null); setComplete(false)
    try {
      const result = await postFile('/ccdi/validate-workbook', 'workbook', file); setCheck(result); setActiveStep(4)
      setNotice('Preliminary structural checks finished. Review all warnings: this is not a CCDI certification or vocabulary approval.')
    } catch (e) { setError(String(e)) } finally { setRunning(false) }
  }
  function autoMatch() {
    const used = new Set<string>()
    setRows(current => current.map(row => {
      if (row.target) { used.add(row.target); return row }
      const key = row.source.toLowerCase().replace(/[^a-z0-9]/g,'')
      const exact = properties.find(p => p.toLowerCase().replace(/[^a-z0-9]/g,'') === key && !used.has(p))
      if (exact) {used.add(exact); return {...row,target:exact}}
      return row
    }))
    setNotice('Exact-name suggestions applied only. Review and confirm every field manually; this is not AI or ontology mapping.')
  }
  async function build() {
    if (!template || !source) return
    setRunning(true); setError(''); setComplete(false)
    try {
      const parsed = advanced ? JSON.parse(manualMapping) : mapping
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed) || !Object.keys(parsed).length) throw new Error('Select at least one source-to-CCDI mapping.')
      if (!advanced && duplicateTargets.length) throw new Error(`Multiple fields target ${duplicateTargets.join(', ')}. Each target property must be unique.`)
      const body = new FormData(); body.append('template', template); body.append('source', source)
      body.append('node', node); body.append('mappings_json', JSON.stringify(parsed)); body.append('accession', accession)
      const response = await fetch(`${api}/ccdi/build-candidate`, { method: 'POST', body })
      if (!response.ok) { const e = await response.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${response.status}`) }
      const blob = await response.blob(); const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = 'ccdi_candidate_package.zip'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 2000)
      setExported(true); setActiveStep(4)
      setNotice('Candidate package downloaded. Open the ZIP, review validation_report.json and upload the candidate_CC_DI_metadata.xlsx below for preliminary structural validation.')
    } catch (e) { setError(String(e)) } finally { setRunning(false) }
  }
  function finish() {
    if (!canComplete) return
    const manifest = {
      title: 'Local CCDI preparation handoff (NOT an official CCDI submission)',
      generated_at_utc: new Date().toISOString(), status: 'local_handoff_prepared',
      source_repository: sourceType, source_accession: accession, source_name: source?.name,
      template_sha256: inspection?.template_sha256, selected_node: node,
      local_validation: check?.summary, disclaimer: 'CCDI curation, access permissions, consent, controlled vocabularies, institutional approvals, and official transfer remain outstanding.',
      next_steps: ['Review all QC warnings and mandatory metadata', 'Confirm appropriate data rights and institutional authorization', `Contact ${CCDI_HELP} for approved integration and submission instructions`, 'Use only CCDI-issued transfer destinations and credentials']
    }
    saveText('ccdi_local_handoff_manifest.json', JSON.stringify(manifest,null,2), 'application/json')
    setComplete(true); setActiveStep(5); setNotice('Local preparation complete. Handoff manifest downloaded. Nothing was transmitted to CCDI.')
  }
  function contactCcdi() {
    const subject = encodeURIComponent('CCDI Track 1 tool integration and data handoff request')
    const body = encodeURIComponent(`Hello CCDI Team,\n\nWe are developing an open-source, AI-assisted interoperability and metadata preparation tool for the CCDI Data Ecosystem. We would like guidance on approved integration/onboarding requirements and the authorized curation/submission handoff process.\n\nOur current software prepares candidate CCDI workbooks with local structural QC and provenance. We are not sending any datasets or credentials in this email.\n\nPlease advise on tool registration/hosting and data submission integration requirements.\n\nThank you.`)
    window.location.href = `mailto:${CCDI_HELP}?subject=${subject}&body=${body}`
  }
  return <div className="ccdi-studio">
    <section className="ccdi-hero">
      <div><p className="eyebrow">Track 1 · Guided interoperability workspace</p><h1>CCDI preparation studio</h1><p>Discover public studies, prepare metadata, review mappings and validate a candidate workbook—all with a clear, auditable handoff.</p><span className="connection-chip"><span className="connection-dot"/> Not connected to CCDI submission services</span></div>
      <div className="ccdi-progress"><strong>{progress}%</strong><span>Local workflow progress</span><div className="progress-track"><i style={{width:`${progress}%`}}/></div><small>{counted.filter(Boolean).length} of {steps.length} milestones completed</small></div>
    </section>
    <div className="ccdi-stepper" aria-label="Preparation stages">{steps.map((step,i) => <button key={step} type="button" className={`${i === activeStep ? 'is-active' : ''} ${counted[i] ? 'is-done' : ''}`} onClick={() => {setActiveStep(i); document.getElementById(`ccdi-stage-${i}`)?.scrollIntoView({behavior:'smooth',block:'start'})}}><span>{counted[i] ? '✓' : i + 1}</span>{step}</button>)}</div>
    {error && <div className="ccdi-alert error" role="alert">{error}<button onClick={()=>setError('')} aria-label="Dismiss error">×</button></div>}
    {notice && <div className="ccdi-alert info" role="status">{notice}<button onClick={()=>setNotice('')} aria-label="Dismiss notice">×</button></div>}
    <div className="ccdi-columns"><div className="ccdi-main">
      <section className="ccdi-card" id="ccdi-stage-0"><div className="ccdi-card-heading"><span className="ccdi-number purple">01</span><div><h2>Find a public study</h2><p>Verify a repository accession to begin. Discovery does not download files.</p></div></div>
        <div className="two"><label className="field"><span>Repository</span><select value={sourceType} onChange={e => {const v=e.target.value as 'gdc'|'geo';setSourceType(v);setSourceLookup(v==='gdc'?'TARGET-NBL':'GSE12345');setSourceInfo('');setSourceLink('')}}><option value="gdc">NCI GDC / TARGET project</option><option value="geo">NCBI GEO study</option></select></label><label className="field"><span>Project / study accession</span><input value={sourceLookup} onChange={e=>setSourceLookup(e.target.value)} placeholder="TARGET-NBL" /></label></div>
        <button className="primary" disabled={running || !sourceLookup.trim()} onClick={lookupSource}>{running ? 'Checking…' : 'Verify accession'}</button>
        {sourceInfo && <div className="ccdi-found"><strong>✓ {sourceInfo}</strong><p>{sourceLink ? <a href={sourceLink} target="_blank" rel="noreferrer">Open repository study and select a permitted public metadata file ↗</a> : 'Review study files in the source repository.'}</p><small>Live accession lookup only. Automatic dataset selection/download has not been implemented.</small></div>}
      </section>
      <section className="ccdi-card" id="ccdi-stage-1"><div className="ccdi-card-heading"><span className="ccdi-number cyan">02</span><div><h2>Choose a source table</h2><p>Use a de-identified, permitted CSV/TSV from GEO, TARGET, or a local cohort.</p></div></div>
        <label className="ccdi-upload"><input type="file" accept=".csv,.tsv" onChange={e=>void selectSource(e.target.files?.[0]||null)}/><span>↑</span><strong>{source ? source.name : 'Select CSV / TSV file'}</strong><small>{source ? `${(source.size / 1024 / 1024).toFixed(2)} MiB · ${sourceHeaders.length} columns` : 'Candidate builder limit: 10 MiB and 5,000 rows. Large files can be profiled separately.'}</small></label>
        {sourceHeaders.length>0 && <details className="ccdi-detail"><summary>View detected source columns ({sourceHeaders.length})</summary><div className="ccdi-tags">{sourceHeaders.map(h=><span key={h}>{h}</span>)}</div></details>}
        <label className="field"><span>Source accession / provenance</span><input value={accession} onChange={e=>setAccession(e.target.value)} placeholder="e.g. TARGET-NBL or GSE…"/></label>
      </section>
      <section className="ccdi-card" id="ccdi-stage-2"><div className="ccdi-card-heading"><span className="ccdi-number blue">03</span><div><h2>Load the CCDI template</h2><p>Inspect the official, versioned Excel workbook to discover real node properties.</p></div></div>
        <a href={CCDI_MODEL} target="_blank" rel="noreferrer">Official CCDI data model releases ↗</a><p><button type="button" className="secondary" onClick={useBundledTemplate} disabled={running}>Use bundled CCDI v2.2.0 template</button></p>
        <label className="ccdi-upload"><input type="file" accept=".xlsx" onChange={e=>{setTemplate(e.target.files?.[0]||null);setInspection(null);setExported(false);setComplete(false)}}/><span>▦</span><strong>{template?.name || 'Choose official CCDI .xlsx template'}</strong><small>Use a blank metadata template from the official release</small></label>
        <button className="primary" disabled={!template||running} onClick={inspect}>{running?'Inspecting…':'Inspect template'}</button>
        {inspection && <div className="ccdi-results"><div className="ccdi-stat-row"><div><strong>{inspection.sheets.length}</strong><span>Node sheets</span></div><div><strong>{inspection.summary.error_count}</strong><span>Structural errors</span></div><div><strong>{inspection.summary.warning_count}</strong><span>Warnings</span></div><div><strong>{inspection.dictionary_property_count ?? 0}</strong><span>Dictionary properties</span></div></div><small>Template SHA-256: <code>{inspection.template_sha256.slice(0,18)}…</code></small><label className="field"><span>Choose target node</span><select value={node} onChange={e=>{setNode(e.target.value);setRows(curr=>curr.map(r=>({...r,target:''})))}}>{inspection.sheets.map(s=><option key={s.name} value={s.name}>{s.name}</option>)}</select></label><details className="ccdi-detail" open><summary>{selectedSheet?.fields.length || 0} properties detected in {node}</summary><div className="ccdi-tags">{selectedSheet?.fields.map(f=><span key={f.name} title={`${f.datatype||""} ${f.required?"Mandatory field":""} ${f.relationship?"Linked identifier":""}`}>{f.required?"★ ":f.relationship?"↔ ":""}{f.name}</span>)}</div></details>{inspection.issues.length>0&&<details className="ccdi-detail"><summary>Template issues ({inspection.issues.length})</summary><ul>{inspection.issues.map((issue,i)=><li key={i}><strong>{issue.level}:</strong> {issue.sheet}: {issue.message}</li>)}</ul></details>}</div>}
      </section>
      <section className="ccdi-card" id="ccdi-stage-3"><div className="ccdi-card-heading"><span className="ccdi-number orange">04</span><div><h2>Review mappings & export</h2><p>Choose exact CCDI target properties. Every mapping requires a human review.</p></div></div>
        <div className="ccdi-toolbar"><span>{rows.filter(r=>r.target).length} of {rows.length} source fields mapped</span><button className="secondary" disabled={!properties.length||!rows.length} onClick={autoMatch}>Suggest exact-name matches</button></div>
        {sourceHeaders.length && inspection ? <div className="ccdi-map-list"><div className="ccdi-map-header"><span>Source field</span><span>CCDI target property</span></div>{rows.map((r,i)=><div className="ccdi-map-row" key={`${r.source}-${i}`}><strong title={r.source}>{r.source}</strong><select aria-label={`CCDI target for ${r.source}`} value={r.target} onChange={e=>setRows(curr=>curr.map((x,j)=>i===j?{...x,target:e.target.value}:x))}><option value="">Leave unmapped</option>{properties.map(p=><option key={p} value={p}>{p}</option>)}</select></div>)}</div> : <p className="ccdi-empty">Upload a source table and inspect a template to use the interactive mapping editor.</p>}
        {duplicateTargets.length>0&&<div className="ccdi-alert error">Duplicate target properties: {Array.from(new Set(duplicateTargets)).join(', ')}</div>}
        <details className="ccdi-detail" open={advanced} onToggle={e=>setAdvanced(e.currentTarget.open)}><summary>Advanced: enter mapping JSON manually</summary><p>When expanded, JSON overrides the visual mapping editor. Only use real source and CCDI property names.</p><textarea rows={5} value={manualMapping} onChange={e=>setManualMapping(e.target.value)} placeholder={'{\n  "patient_id": "participant_id"\n}'}/></details>
        <button className="primary" disabled={!template||!source||!inspection||inspection.summary.error_count>0||running||(!advanced && (!rows.some(r=>r.target)||duplicateTargets.length>0))} onClick={build}>{running?'Preparing…':'Download candidate ZIP + QC + provenance'}</button>
        {exported&&<div className="ccdi-found">✓ Package exported locally. This is a candidate workbook, not an approved CCDI submission.</div>}
      </section>
      <section className="ccdi-card" id="ccdi-multinode"><div className="ccdi-card-heading"><span className="ccdi-number cyan">+</span><div><h2>Multi-sheet import · CCDI v2.2.0</h2><p>Prepare participant, diagnosis, sample and file metadata together. This preserves the 35-tab official workbook and validates links across selected sheets.</p></div></div>
        <div className="ccdi-feature-grid"><div className="ccdi-mini"><strong>Required fields</strong><p>Detect blank yellow mandatory properties in populated records.</p></div><div className="ccdi-mini"><strong>Controlled terms</strong><p>Check values against terms bundled in the workbook.</p></div><div className="ccdi-mini"><strong>Linked records</strong><p>Check participant and sample reference identifiers across imported tables.</p></div></div>
        <p><strong>1.</strong> Create a ZIP with small CSV/TSV source files such as <code>participant.csv</code>, <code>diagnosis.csv</code>, <code>sample.csv</code>. <strong>2.</strong> Supply the mapping below using real source headers and real target properties. <strong>3.</strong> Export and validate the candidate package.</p>
        <label className="ccdi-upload"><input type="file" accept=".zip,application/zip" onChange={e=>setMultiZip(e.target.files?.[0]||null)}/><span>▤</span><strong>{multiZip?.name||'Select multi-node CSV/TSV ZIP'}</strong><small>ZIP ≤ 30 MiB; individual source tables ≤ 10 MiB / 5,000 rows. No data is sent to CCDI.</small></label>
        <label className="field"><span>Multi-node mapping JSON</span><textarea rows={9} value={multiJson} onChange={e=>setMultiJson(e.target.value)} placeholder={'{\n  "participant": {\n    "file": "participant.csv",\n    "mappings": { "patient_id": "participant_id", "sex": "sex_at_birth" }\n  },\n  "diagnosis": {\n    "file": "diagnosis.csv",\n    "mappings": { "patient_id": "participant.participant_id", "diagnosis_id": "diagnosis_id" }\n  }\n}'}/></label>
        <button className="primary" disabled={!template||!inspection||!multiZip||!multiJson.trim()||running} onClick={buildMulti}>{running?'Building…':'Build multi-sheet candidate package'}</button>
        {multiExported&&<div className="ccdi-found">✓ Multi-sheet candidate downloaded. Validation and curator review are still required.</div>}
      </section>
      <section className="ccdi-card" id="ccdi-stage-4"><div className="ccdi-card-heading"><span className="ccdi-number green">05</span><div><h2>Validate the populated workbook</h2><p>Open the exported ZIP, extract the workbook, and upload it for local structural checks.</p></div></div>
        <label className="ccdi-upload"><input type="file" accept=".xlsx" onChange={e=>{if(e.target.files?.[0])void validateWorkbook(e.target.files[0])}}/><span>✓</span><strong>Select populated CCDI workbook (.xlsx)</strong><small>Checks workbook structure, yellow required fields, controlled terms and linked identifiers; not curator approval</small></label>
        {check&&<div className="ccdi-results"><div className="ccdi-stat-row"><div><strong>{check.summary.error_count}</strong><span>Structural errors</span></div><div><strong>{check.summary.warning_count}</strong><span>Warnings</span></div></div><p><strong>{check.status}</strong> · Preliminary local result only</p>{check.issues.length>0&&<details className="ccdi-detail" open><summary>View findings ({check.issues.length})</summary><ul>{check.issues.map((issue,i)=><li key={i}>{issue.level}: {issue.sheet}: {issue.message}</li>)}</ul></details>}</div>}
      </section>
      <section className="ccdi-card ccdi-final" id="ccdi-stage-5"><div className="ccdi-card-heading"><span className="ccdi-number purple">06</span><div><h2>Complete & request CCDI handoff</h2><p>Finish local preparation. No data is transmitted to CCDI by this action.</p></div></div>
        <div className="ccdi-handoff-state"><strong>Integration status: Awaiting CCDI authorization</strong><p>Official CCDI curation, full metadata review, consent assessment, controlled-access registration and approved file transfer are separate processes.</p></div>
        <label className="ccdi-check"><input type="checkbox" checked={agreed} onChange={e=>setAgreed(e.target.checked)}/><span>I understand that local structural validation is not CCDI acceptance or authorization to transfer data, and that all access, privacy and institutional requirements must be reviewed.</span></label>
        <div className="ccdi-actions"><button className="primary" disabled={!canComplete} onClick={finish}>{complete ? 'Download handoff manifest again' : 'Complete local preparation'}</button><button className="secondary" type="button" onClick={contactCcdi}>Request CCDI integration guidance ↗</button></div>
        {!canComplete && <small className="ccdi-hint">To enable completion: export the candidate package, validate a populated workbook without structural errors, and acknowledge the review requirement.</small>}
        {complete && <div className="ccdi-found">✓ Local handoff manifest generated. <strong>No CCDI transfer occurred.</strong> Contact the CCDI team to arrange an authorized next step.</div>}
      </section>
    </div><aside className="ccdi-aside">
      <div className="ccdi-side-card"><h3>How this works</h3><p>Follow the six stages to prepare a traceable metadata package.</p><ol>{steps.map((s,i)=><li key={s} className={counted[i]?'ready':''}><span>{counted[i]?'✓':i+1}</span>{s}</li>)}</ol></div>
      <div className="ccdi-side-card gradient"><h3>CCDI ecosystem integration</h3><p>This app is an independent prototype, not an NCI-operated service.</p><p><strong>Tool delivery:</strong> open-source GitHub or an NCI-approved hosting arrangement.</p><p><strong>Data delivery:</strong> CCDI curation and approved transfer workflow, after authorization.</p><a href="https://ccdi.cancer.gov/Submission_Guide.pdf" target="_blank" rel="noreferrer">Read official submission guidance ↗</a></div>
      <div className="ccdi-side-card"><h3>Security & limitations</h3><p>Do not upload protected clinical or controlled-access genomic data without authorization. Discovery is metadata-only. Candidate export is currently limited to small CSV/TSV inputs.</p></div>
    </aside></div>
  </div>
}
