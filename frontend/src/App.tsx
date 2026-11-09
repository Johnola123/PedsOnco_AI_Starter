import { FormEvent, useEffect, useMemo, useState } from 'react'
import CcdiReadiness from './CcdiReadiness'
import {
  Cohort,
  Dataset,
  DatasetProfile,
  WorkspaceRecord,
  createWorkspaceRecord,
  deleteWorkspaceRecord,
  getCohortDatasets,
  getCohortExportManifest,
  getCohorts,
  getDatasetProfile,
  getDatasets,
  getDownloadUrl,
  previewDatasetDelete,
  deleteDatasetConfirmed,
  getHealth,
  getWorkspaceRecords,
  Health,
  importExternalUrl,
  mergeCohorts,
  uploadFileDirect,
  validateHarmonization,
  validateIntegration,
  HarmonizationValidation,
  IntegrationValidation,
} from './api'

type View = 'cohorts' | 'add' | 'workspace' | 'merge' | 'ccdi'
type WorkspaceTab = 'files' | 'inspect' | 'harmonize' | 'edit' | 'integrate' | 'explore' | 'export'
type IntakeMode = 'files' | 'url'

type MappingRow = { source: string; canonical: string; confidence: number; status: 'accept' | 'review' | 'reject'; reason?: string }
type ConfirmState = { title: string; message: string; confirmLabel?: string; tone?: 'default' | 'danger'; action: () => void | Promise<void> } | null

const CANONICAL_ALIASES: Record<string, string[]> = {
  participant_id: ['participant_id', 'patient_id', 'patientid', 'subject_id', 'subjectid', 'case_id'],
  sample_id: ['sample_id', 'sampleid', 'specimen_id', 'biospecimen_id'],
  diagnosis: ['diagnosis', 'diagnosis_name', 'disease', 'disease_type', 'cancer_type'],
  age_at_diagnosis: ['age_at_diagnosis', 'age_dx', 'agedx', 'diagnosis_age', 'age_at_dx'],
  sex: ['sex', 'gender', 'biological_sex'],
  race: ['race', 'race_group', 'racegroup'],
  ethnicity: ['ethnicity', 'ethnic_group'],
  vital_status: ['vital_status', 'status', 'survival_status'],
  days_to_death: ['days_to_death', 'os_days', 'overall_survival_days'],
  treatment_response: ['treatment_response', 'response', 'best_response'],
  file_name: ['file_name', 'filename', 'file'],
  library_id: ['library_id', 'libraryid'],
}

const CANONICAL_CATALOG = [
  { name: 'participant_id', label: 'Participant ID', group: 'Participant', type: 'identifier' },
  { name: 'sample_id', label: 'Sample ID', group: 'Biospecimen', type: 'identifier' },
  { name: 'diagnosis', label: 'Diagnosis', group: 'Clinical', type: 'categorical' },
  { name: 'age_at_diagnosis', label: 'Age at diagnosis', group: 'Clinical', type: 'number' },
  { name: 'sex', label: 'Sex', group: 'Demographics', type: 'categorical' },
  { name: 'race', label: 'Race', group: 'Demographics', type: 'categorical' },
  { name: 'ethnicity', label: 'Ethnicity', group: 'Demographics', type: 'categorical' },
  { name: 'vital_status', label: 'Vital status', group: 'Outcome', type: 'categorical' },
  { name: 'days_to_death', label: 'Days to death', group: 'Outcome', type: 'number' },
  { name: 'treatment_response', label: 'Treatment response', group: 'Treatment', type: 'categorical' },
  { name: 'file_name', label: 'File name', group: 'File metadata', type: 'string' },
  { name: 'library_id', label: 'Library ID', group: 'Sequencing', type: 'identifier' },
  { name: 'study_id', label: 'Study ID', group: 'Study', type: 'identifier' },
  { name: 'study_name', label: 'Study name', group: 'Study', type: 'string' },
  { name: 'consent_group', label: 'Consent group', group: 'Study', type: 'categorical' },
  { name: 'treatment_type', label: 'Treatment type', group: 'Treatment', type: 'categorical' },
  { name: 'event_free_survival_days', label: 'Event-free survival days', group: 'Outcome', type: 'number' },
  { name: 'event_free_survival_status', label: 'Event-free survival status', group: 'Outcome', type: 'categorical' },
  { name: 'tumor_site', label: 'Tumor site', group: 'Clinical', type: 'categorical' },
  { name: 'histology', label: 'Histology', group: 'Clinical', type: 'categorical' },
  { name: 'stage', label: 'Stage', group: 'Clinical', type: 'categorical' },
  { name: 'molecular_subtype', label: 'Molecular subtype', group: 'Molecular', type: 'categorical' },
  { name: 'specimen_type', label: 'Specimen type', group: 'Biospecimen', type: 'categorical' },
]

function formatBytes(bytes: number) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const power = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** power).toFixed(power === 0 ? 0 : 1)} ${units[power]}`
}

function extension(name: string) {
  const lower = name.toLowerCase()
  for (const ext of ['fastq.gz', 'fq.gz', 'vcf.gz', 'fasta.gz', 'fa.gz']) {
    if (lower.endsWith(`.${ext}`)) return ext
  }
  return lower.includes('.') ? lower.split('.').pop() || 'file' : 'file'
}

function prettyType(name: string) {
  const ext = extension(name)
  const map: Record<string, string> = {
    xlsx: 'Workbook', xlsm: 'Workbook', csv: 'CSV', tsv: 'TSV', json: 'JSON', ndjson: 'JSON',
    fasta: 'FASTA', fa: 'FASTA', fastq: 'FASTQ', fq: 'FASTQ', 'fastq.gz': 'FASTQ', bam: 'BAM', cram: 'CRAM',
    vcf: 'VCF', 'vcf.gz': 'VCF', maf: 'MAF', png: 'Image', jpg: 'Image', jpeg: 'Image', dcm: 'DICOM',
    parquet: 'Parquet', zip: 'Archive',
  }
  return map[ext] || ext.toUpperCase()
}

function normalize(value: string) {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
}

function suggestMapping(source: string): MappingRow {
  const n = normalize(source)
  for (const [canonical, aliases] of Object.entries(CANONICAL_ALIASES)) {
    if (normalize(canonical) === n) return { source, canonical, confidence: 100, status: 'accept', reason: 'Exact canonical name match' }
    if (aliases.some((alias) => normalize(alias) === n)) return { source, canonical, confidence: 96, status: 'accept', reason: 'Known CCDI-oriented alias match' }
  }
  for (const [canonical, aliases] of Object.entries(CANONICAL_ALIASES)) {
    if ([canonical, ...aliases].some((alias) => n.includes(normalize(alias)) || normalize(alias).includes(n))) {
      return { source, canonical, confidence: 82, status: 'review', reason: 'Partial semantic/name similarity' }
    }
  }
  return { source, canonical: n || source, confidence: 55, status: 'review', reason: 'No strong catalog match; review required' }
}

function tablesFromProfile(profile?: DatasetProfile | null) {
  if (!profile) return []
  if (profile.profile.sheets?.length) return profile.profile.sheets
  if (profile.profile.tables?.length) return profile.profile.tables
  if (profile.profile.paths?.length) return [{ name: 'JSON paths', rows: profile.profile.records || 1, columns: profile.profile.paths.length, role: 'json', fields: profile.profile.paths.map((name) => ({ name, inferred_type: 'unknown', sample_values: [] })) }]
  return []
}

function fieldsForTable(profile?: DatasetProfile | null, tableName?: string) {
  const tables = tablesFromProfile(profile)
  const table = tables.find((item) => item.name === tableName) || tables.find((item) => item.fields?.length) || tables[0]
  if (!table) return []
  if (table.fields?.length) return table.fields
  const header = table.preview?.[0]
  return Array.isArray(header) ? header.map((value) => ({ name: String(value ?? '').trim(), inferred_type: 'unknown', sample_values: [] })).filter((f) => f.name) : []
}

function allFieldsFromProfile(profile?: DatasetProfile | null) {
  const seen = new Map<string, { name: string; inferred_type: string; sample_values: string[] }>()
  for (const table of tablesFromProfile(profile)) {
    for (const field of table.fields || []) if (!seen.has(field.name)) seen.set(field.name, field)
  }
  return Array.from(seen.values())
}


export default function App() {
  const [view, setView] = useState<View>('cohorts')
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>('files')
  const [health, setHealth] = useState<Health | null>(null)
  const [cohorts, setCohorts] = useState<Cohort[]>([])
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  const [projectName, setProjectName] = useState('')
  const [intakeMode, setIntakeMode] = useState<IntakeMode>('files')
  const [files, setFiles] = useState<File[]>([])
  const [progress, setProgress] = useState<Record<string, number>>({})
  const [externalUrl, setExternalUrl] = useState('')
  const [externalFilename, setExternalFilename] = useState('')
  const [bearerToken, setBearerToken] = useState('')

  const [selectedCohort, setSelectedCohort] = useState('')
  const [cohortFiles, setCohortFiles] = useState<Dataset[]>([])
  const [profiles, setProfiles] = useState<Record<number, DatasetProfile>>({})
  const [selectedDatasetId, setSelectedDatasetId] = useState<number | null>(null)
  const [profilingId, setProfilingId] = useState<number | null>(null)
  const [workspaceRecords, setWorkspaceRecords] = useState<WorkspaceRecord[]>([])
  const [mappings, setMappings] = useState<MappingRow[]>([])
  const [selectedTable, setSelectedTable] = useState('')
  const [mappingValidation, setMappingValidation] = useState<HarmonizationValidation | null>(null)
  const [integrationValidation, setIntegrationValidation] = useState<IntegrationValidation | null>(null)
  const [draggedSourceField, setDraggedSourceField] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const [workspaceDragActive, setWorkspaceDragActive] = useState(false)
  const [confirmState, setConfirmState] = useState<ConfirmState>(null)

  const [editOperation, setEditOperation] = useState('rename field')
  const [editTable, setEditTable] = useState('')
  const [editField, setEditField] = useState('')
  const [editFieldSearch, setEditFieldSearch] = useState('')
  const [editValue, setEditValue] = useState('')
  const [leftDataset, setLeftDataset] = useState('')
  const [leftKey, setLeftKey] = useState('participant_id')
  const [rightDataset, setRightDataset] = useState('')
  const [rightKey, setRightKey] = useState('participant_id')
  const [relationship, setRelationship] = useState('1:1')

  const [mergeName, setMergeName] = useState('')
  const [mergeSources, setMergeSources] = useState<string[]>([])
  const [mergeNotes, setMergeNotes] = useState('')

  async function refresh() {
    const [h, c, d] = await Promise.all([getHealth(), getCohorts(), getDatasets()])
    setHealth(h)
    setCohorts(c)
    setDatasets(d)
  }

  useEffect(() => { refresh().catch((error) => setMessage(String(error))) }, [])

  const sourceCohorts = useMemo(() => cohorts.filter((cohort) => cohort.kind === 'source'), [cohorts])
  const selectedDataset = cohortFiles.find((item) => item.id === selectedDatasetId) || null
  const selectedProfile = selectedDatasetId ? profiles[selectedDatasetId] : undefined
  const selectedTables = tablesFromProfile(selectedProfile)
  const selectedFields = fieldsForTable(selectedProfile, selectedTable)
  const editFields = fieldsForTable(selectedProfile, editTable)
  const filteredEditFields = editFields.filter((field) => !editFieldSearch.trim() || field.name.toLowerCase().includes(editFieldSearch.trim().toLowerCase()))
  const leftProfile = leftDataset ? profiles[Number(leftDataset)] : undefined
  const rightProfile = rightDataset ? profiles[Number(rightDataset)] : undefined
  const leftFields = allFieldsFromProfile(leftProfile)
  const rightFields = allFieldsFromProfile(rightProfile)
  const totalTables = Object.values(profiles).reduce((sum, p) => sum + p.table_count, 0)
  const formats = Array.from(new Set(cohortFiles.map((file) => prettyType(file.original_name))))

  async function loadWorkspace(name: string, tab: WorkspaceTab = 'files') {
    setSelectedCohort(name)
    setWorkspaceTab(tab)
    setMessage('')
    try {
      const [filesForCohort, records] = await Promise.all([getCohortDatasets(name), getWorkspaceRecords(name)])
      setCohortFiles(filesForCohort)
      setWorkspaceRecords(records)
      const first = filesForCohort[0]
      setSelectedDatasetId(first?.id || null)
      setView('workspace')
    } catch (error) { setMessage(String(error)) }
  }

  function addToCohort(name: string) {
    setProjectName(name)
    setFiles([])
    setMessage('')
    setView('add')
  }

  function appendFiles(incoming: File[]) {
    setFiles((current) => {
      const seen = new Set(current.map((file) => `${file.name}:${file.size}:${file.lastModified}`))
      return [...current, ...incoming.filter((file) => !seen.has(`${file.name}:${file.size}:${file.lastModified}`))]
    })
  }

  function handleDrop(event: React.DragEvent<HTMLElement>) {
    event.preventDefault()
    setDragActive(false)
    appendFiles(Array.from(event.dataTransfer.files || []))
  }

  async function uploadFilesToWorkspace(incoming: File[], inspectAfter = false) {
    if (!selectedCohort || !incoming.length) return
    setBusy(true); setMessage('')
    try {
      for (const file of incoming) {
        const key = `${file.name}:${file.size}`
        await uploadFileDirect(file, selectedCohort, (value) => setProgress((current) => ({ ...current, [key]: value })))
      }
      const refreshed = await getCohortDatasets(selectedCohort)
      setCohortFiles(refreshed)
      await refresh()
      setMessage(`${incoming.length} file${incoming.length === 1 ? '' : 's'} added to ${selectedCohort}.`)
      if (inspectAfter) {
        const newest = [...refreshed].sort((a, b) => b.id - a.id)[0]
        if (newest) await inspectDataset(newest, 'inspect')
      }
    } catch (error) { setMessage(String(error)) } finally { setBusy(false); setWorkspaceDragActive(false); setProgress({}) }
  }

  function requestConfirm(state: NonNullable<ConfirmState>) { setConfirmState(state) }

  async function runConfirmedAction() {
    if (!confirmState) return
    const action = confirmState.action
    setConfirmState(null)
    await action()
  }

  async function submitFiles(event: FormEvent) {
    event.preventDefault()
    const cohort = projectName.trim()
    if (!cohort) return setMessage('Enter a cohort name or choose an existing cohort.')
    if (!files.length) return setMessage('Choose at least one file.')
    setBusy(true); setMessage('')
    try {
      for (const file of files) {
        const key = `${file.name}:${file.size}`
        await uploadFileDirect(file, cohort, (value) => setProgress((current) => ({ ...current, [key]: value })))
      }
      setMessage(`${files.length} file${files.length === 1 ? '' : 's'} added to ${cohort}.`)
      setFiles([]); setProgress({})
      await refresh()
      await loadWorkspace(cohort, 'files')
    } catch (error) { setMessage(String(error)) } finally { setBusy(false) }
  }

  async function submitUrl(event: FormEvent) {
    event.preventDefault()
    const cohort = projectName.trim()
    if (!cohort) return setMessage('Enter a cohort name or choose an existing cohort.')
    setBusy(true); setMessage('')
    try {
      await importExternalUrl({ projectName: cohort, url: externalUrl, filename: externalFilename, bearerToken })
      setExternalUrl(''); setExternalFilename(''); setBearerToken('')
      await refresh(); await loadWorkspace(cohort, 'files')
      setMessage(`External data added to ${cohort}.`)
    } catch (error) { setMessage(String(error)) } finally { setBusy(false) }
  }

  async function inspectDataset(dataset: Dataset, goTo: WorkspaceTab = 'inspect') {
    setSelectedDatasetId(dataset.id)
    setProfilingId(dataset.id)
    setMessage('')
    try {
      const result = await getDatasetProfile(dataset.id)
      setProfiles((current) => ({ ...current, [dataset.id]: result }))
      if (goTo === 'harmonize') {
        const tables = tablesFromProfile(result)
        const table = tables.find((item) => item.name.toLowerCase() === 'participant') || tables.find((item) => item.role !== 'reference' && item.fields?.length) || tables.find((item) => item.fields?.length) || tables[0]
        setSelectedTable(table?.name || '')
        setMappings(fieldsForTable(result, table?.name).map((field) => suggestMapping(field.name)))
        setMappingValidation(null)
      }
      setWorkspaceTab(goTo)
    } catch (error) { setMessage(String(error)) } finally { setProfilingId(null) }
  }

  async function profileAll() {
    setBusy(true); setMessage('')
    try {
      const entries = await Promise.all(cohortFiles.map(async (file) => [file.id, await getDatasetProfile(file.id)] as const))
      setProfiles(Object.fromEntries(entries))
      setMessage(`Profiled ${entries.length} cohort file${entries.length === 1 ? '' : 's'}.`)
    } catch (error) { setMessage(String(error)) } finally { setBusy(false) }
  }

  async function ensureProfile(datasetId: number) {
    if (profiles[datasetId]) return profiles[datasetId]
    const result = await getDatasetProfile(datasetId)
    setProfiles((current) => ({ ...current, [datasetId]: result }))
    return result
  }

  async function prepareEditDataset(datasetId: number) {
    setSelectedDatasetId(datasetId)
    setEditField('')
    setEditFieldSearch('')
    const result = await ensureProfile(datasetId)
    const tables = tablesFromProfile(result)
    const preferred = tables.find((item) => item.name.toLowerCase() === 'participant') || tables.find((item) => item.role !== 'reference' && item.fields?.length) || tables.find((item) => item.fields?.length) || tables[0]
    setEditTable(preferred?.name || '')
  }

  async function reloadRecords() {
    if (selectedCohort) setWorkspaceRecords(await getWorkspaceRecords(selectedCohort))
  }

  function generateMappingSuggestions(tableName = selectedTable) {
    const fields = fieldsForTable(selectedProfile, tableName)
    setMappings(fields.map((field) => suggestMapping(field.name)))
    setMappingValidation(null)
  }

  function mapSourceToCanonical(source: string, canonical: string) {
    setMappings((current) => current.map((row) => row.source === source ? { ...row, canonical, status: 'review', reason: 'Manually dragged/edited by reviewer' } : row))
    setMappingValidation(null)
  }

  async function validateAndSaveHarmonization() {
    if (!selectedCohort || !selectedDataset) return
    setBusy(true); setMessage('')
    try {
      const validation = await validateHarmonization({ datasetId: selectedDataset.id, tableName: selectedTable || null, mappings })
      setMappingValidation(validation)
      if (!validation.valid) {
        setMessage('Validation found blocking issues. Review the highlighted mappings before confirmation.')
        return
      }
      const warningCount = validation.issues.filter((issue) => issue.level === 'warning').length
      requestConfirm({
        title: 'Confirm reviewed harmonization?',
        message: `Validation passed with score ${validation.score}/100. ${validation.accepted_count} accepted, ${validation.review_count} still marked review, ${validation.rejected_count} rejected${warningCount ? `, ${warningCount} warning(s)` : ''}. Confirm to record this reviewed mapping and validation snapshot in provenance.`,
        confirmLabel: 'Confirm & record provenance',
        action: async () => {
          await createWorkspaceRecord(selectedCohort, 'harmonization', `Mappings · ${selectedDataset.original_name} · ${selectedTable || 'default table'}`, {
            workflow: 'AI proposes → user reviews/drags/edits → system validates → user confirms',
            dataset_id: selectedDataset.id, dataset_name: selectedDataset.original_name, table_name: selectedTable || null, mappings, validation,
            confirmed_at: new Date().toISOString(), proposal_engine: 'transparent alias + name similarity MVP',
          })
          await reloadRecords()
          setMessage('Confirmed harmonization recorded with validation evidence and provenance. Raw data remain unchanged.')
        },
      })
    } catch (error) { setMessage(String(error)) } finally { setBusy(false) }
  }

  async function saveEdit(event: FormEvent, confirmed = false) {
    event.preventDefault()
    if (!selectedCohort || !selectedDataset) return setMessage('Choose a file first.')
    if (!confirmed && ['drop field', 'filter rows', 'deduplicate'].includes(editOperation)) {
      requestConfirm({ title: 'Save this transformation recipe?', message: `“${editOperation}” can change the analysis-ready working view. The raw source remains immutable and the recipe can be removed later.`, confirmLabel: 'Save recipe', action: () => saveEdit({ preventDefault() {} } as FormEvent, true) })
      return
    }
    setBusy(true)
    try {
      await createWorkspaceRecord(selectedCohort, 'edit', `${editOperation} · ${selectedDataset.original_name}`, {
        dataset_id: selectedDataset.id, dataset_name: selectedDataset.original_name, operation: editOperation,
        field: editField, value: editValue,
      })
      setEditField(''); setEditValue(''); await reloadRecords()
      setMessage('Edit recipe saved to the working layer. Raw file was not overwritten.')
    } catch (error) { setMessage(String(error)) } finally { setBusy(false) }
  }

  async function saveIntegration(event: FormEvent, confirmed = false, validationSnapshot?: IntegrationValidation) {
    event.preventDefault()
    if (!selectedCohort || !leftDataset || !rightDataset) return setMessage('Choose two files/tables to relate.')
    if (leftDataset === rightDataset) return setMessage('Choose two different files.')
    const left = cohortFiles.find((d) => String(d.id) === leftDataset)
    const right = cohortFiles.find((d) => String(d.id) === rightDataset)
    if (!confirmed) {
      setBusy(true); setMessage('')
      try {
        const validation = await validateIntegration({
          leftDatasetId: Number(leftDataset), leftKey, rightDatasetId: Number(rightDataset), rightKey, relationship,
        })
        setIntegrationValidation(validation)
        if (!validation.valid) {
          setMessage('Integration validation found blocking issues. Review the join keys before continuing.')
          return
        }
        const warnings = validation.issues.filter((issue) => issue.level === 'warning').length
        requestConfirm({
          title: 'Confirm validated integrated view?',
          message: `System validation passed for ${left?.original_name || 'left source'} (${leftKey}) ↔ ${right?.original_name || 'right source'} (${rightKey}) as ${relationship}${warnings ? ` with ${warnings} warning(s)` : ''}. Confirm to record the relationship and validation snapshot. Raw files remain unchanged.`,
          confirmLabel: 'Confirm & record',
          action: () => saveIntegration({ preventDefault() {} } as FormEvent, true, validation),
        })
      } catch (error) { setMessage(String(error)) } finally { setBusy(false) }
      return
    }
    setBusy(true)
    try {
      await createWorkspaceRecord(selectedCohort, 'integration', `${left?.original_name} ↔ ${right?.original_name}`, {
        left_dataset_id: Number(leftDataset), left_dataset: left?.original_name, left_key: leftKey,
        right_dataset_id: Number(rightDataset), right_dataset: right?.original_name, right_key: rightKey, relationship,
        validation: validationSnapshot || integrationValidation, confirmed_at: new Date().toISOString(),
      })
      await reloadRecords(); setMessage('Validated integration relationship recorded as a non-destructive cohort view.')
    } catch (error) { setMessage(String(error)) } finally { setBusy(false) }
  }

  async function requestDeleteDataset(dataset: Dataset) {
    if (busy) return
    setBusy(true)
    try {
      const impact = await previewDatasetDelete(dataset.id)
      const related = impact.dependent_records.map((record) => `• ${record.type}: ${record.name}`)
      const lines = [
        `Delete “${impact.filename}” (${formatBytes(impact.size_bytes)}) from cohort “${impact.cohort}”?`,
        '',
        'The following will be permanently deleted:',
        '• Original uploaded source object from this application’s storage',
        ...(impact.has_source_metadata ? ['• Source/import provenance metadata'] : []),
        ...(impact.has_profile ? ['• Cached profiling results and previews'] : []),
        ...related,
        ...(related.length === 0 ? ['• No saved mapping, edit, or integration records reference this file'] : []),
        '',
        `${impact.other_files_preserved} other source file(s) in this cohort will remain untouched.`,
        ...(impact.merged_views_affected.length ? [
          `Cross-cohort views that reference this cohort (${impact.merged_views_affected.join(', ')}) will NOT be deleted, but may become incomplete.`,
        ] : []),
        'This will not delete the upstream GEO/GDC file or any downloaded copies outside this application.',
        'This action cannot be undone.',
      ]
      requestConfirm({
        title: 'Permanently delete source file and related data?',
        message: lines.join('\n'), confirmLabel: 'Yes, delete file and related data', tone: 'danger',
        action: async () => {
          setBusy(true)
          try {
            const result = await deleteDatasetConfirmed(dataset.id, impact.token)
            const remaining = await getCohortDatasets(impact.cohort)
            setCohortFiles(remaining)
            setWorkspaceRecords(await getWorkspaceRecords(impact.cohort))
            setProfiles((current) => { const next = { ...current }; delete next[dataset.id]; return next })
            if (selectedDatasetId === dataset.id) {
              setSelectedDatasetId(remaining[0]?.id || null)
              setSelectedTable(''); setMappings([]); setMappingValidation(null); setIntegrationValidation(null)
            }
            setLeftDataset((v) => v === String(dataset.id) ? '' : v)
            setRightDataset((v) => v === String(dataset.id) ? '' : v)
            await refresh()
            setMessage(result.storage_warning || `Deleted ${dataset.original_name} and ${result.removed_workspace_records} related workspace record(s).`)
          } catch (error) { setMessage(`Delete unsuccessful: ${String(error)}`) }
          finally { setBusy(false) }
        },
      })
    } catch (error) { setMessage(`Could not review deletion impact: ${String(error)}`) }
    finally { setBusy(false) }
  }

  async function removeRecord(recordId: number) {
    if (!selectedCohort) return
    requestConfirm({
      title: 'Remove saved workspace decision?',
      message: 'This removes the saved mapping/edit/integration decision from the working layer. Your original source file will not be changed.',
      confirmLabel: 'Remove decision',
      tone: 'danger',
      action: async () => { await deleteWorkspaceRecord(selectedCohort, recordId); await reloadRecords(); setMessage('Saved workspace decision removed.') },
    })
  }

  async function createMerge(event: FormEvent, confirmed = false) {
    event.preventDefault()
    if (!mergeName.trim()) return setMessage('Enter a name for the merged cohort.')
    if (mergeSources.length < 2) return setMessage('Select at least two cohorts to merge.')
    if (!confirmed) {
      requestConfirm({ title: 'Create cross-cohort view?', message: `Create “${mergeName.trim()}” from ${mergeSources.length} source cohorts? The sources remain unchanged and traceable.`, confirmLabel: 'Create merged view', action: () => createMerge({ preventDefault() {} } as FormEvent, true) })
      return
    }
    setBusy(true); setMessage('')
    try {
      await mergeCohorts(mergeName.trim(), mergeSources, mergeNotes)
      setMessage(`Cross-cohort merged view “${mergeName.trim()}” created. Source cohorts remain unchanged.`)
      setMergeName(''); setMergeSources([]); setMergeNotes(''); await refresh(); setView('cohorts')
    } catch (error) { setMessage(String(error)) } finally { setBusy(false) }
  }

  async function download(dataset: Dataset) {
    try { window.open(await getDownloadUrl(dataset.id), '_blank', 'noopener,noreferrer') }
    catch (error) { setMessage(String(error)) }
  }

  async function exportManifest() {
    if (!selectedCohort) return
    const manifest = await getCohortExportManifest(selectedCohort)
    const blob = new Blob([JSON.stringify(manifest, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url; link.download = `${selectedCohort.replace(/[^a-z0-9_-]+/gi, '_')}_workspace_manifest.json`; link.click()
    URL.revokeObjectURL(url)
  }

  function toggleMergeSource(name: string) {
    setMergeSources((current) => current.includes(name) ? current.filter((item) => item !== name) : [...current, name])
  }

  const nav: Array<[View, string, string]> = [['cohorts', 'Cohorts', '◫'], ['add', 'Add data', '+'], ['workspace', 'Workspace', '▤'], ['merge', 'Cross-cohort merge', '⇄'], ['ccdi', 'CCDI preparation', '✓']]
  const pageTips: Record<View, { title: string; detail: string; action: string }> = {
    cohorts: {title:'Start with a cohort', detail:'Browse your registered cohorts or import a new public or permitted dataset. Original data stays preserved.', action:'Add cohort'},
    add: {title:'Data intake', detail:'Upload source files or register a permitted direct source URL. Do not import restricted human data without approval.', action:'Browse cohorts'},
    workspace: {title:'Prepare, review, and trace', detail:'Use the workspace tabs in order. Every mapping and edit remains reviewable before export.', action:'CCDI preparation'},
    merge: {title:'Cross-cohort integration', detail:'Combine only compatible, reviewed data and verify join keys before downstream use.', action:'Browse cohorts'},
    ccdi: {title:'CCDI handoff is separate from submission', detail:'Prepare and validate a candidate workbook locally. Official CCDI transfer requires authorization.', action:'Browse cohorts'},
  }
  const workspaceTabs: WorkspaceTab[] = ['files', 'inspect', 'harmonize', 'edit', 'integrate', 'explore', 'export']

  return <div className="app">
    <header className="topbar">
      <button className="brand" type="button" onClick={() => setView('cohorts')}><span className="brand-dot">P</span><span><strong>PedsOnco AI</strong><small>CCDI interoperability studio · Milestone 1</small></span></button>
      <div className={`health ${health?.status === 'ok' ? 'ok' : ''}`}><i />{health?.status === 'ok' ? 'Connected' : 'Checking'}</div>
    </header>
    <div className="layout">
      <nav className="nav" aria-label="Primary navigation">{nav.map(([id, label, symbol]) => <button key={id} type="button" className={view === id ? 'active' : ''} onClick={() => id === 'workspace' && !selectedCohort ? setView('cohorts') : setView(id)}><span className="nav-icon" aria-hidden="true">{symbol}</span>{label}</button>)}</nav>
      <main>
        <div className="page-guide" role="region" aria-label="Page guidance"><div><span className="guide-label">WORKFLOW GUIDE</span><strong>{pageTips[view].title}</strong><p>{pageTips[view].detail}</p></div><button className="guide-button" type="button" onClick={() => setView(view === 'cohorts' ? 'add' : view === 'workspace' ? 'ccdi' : 'cohorts')}>{pageTips[view].action} <span aria-hidden="true">→</span></button></div>
        {message && <div className="message" role="status">{message}<button type="button" onClick={() => setMessage('')}>×</button></div>}

        {view === 'ccdi' && <CcdiReadiness />}
        {view === 'cohorts' && <>
          <section className="intro"><div><p className="eyebrow">Cohort-centered workflow</p><h1>Prepare each cohort from raw files to analysis-ready exports.</h1><p>Each cohort now has its own Files → Inspect → Harmonize → Edit → Integrate → Explore → Export workspace. Cross-cohort merging is intentionally separate.</p></div><button className="primary" type="button" onClick={() => { setProjectName(''); setView('add') }}>Add cohort data</button></section>
          <section className="stats"><article><span>Source cohorts</span><strong>{sourceCohorts.length}</strong></article><article><span>Cross-cohort views</span><strong>{cohorts.filter((c) => c.kind === 'merged').length}</strong></article><article><span>Registered files</span><strong>{datasets.length}</strong></article><article><span>Storage</span><strong>{formatBytes(datasets.reduce((sum, item) => sum + item.size_bytes, 0))}</strong></article></section>
          <section className="section-head"><div><h2>Your cohorts</h2><p>Open a cohort to manage every file, mapping, edit recipe, relationship, exploration and export in one place.</p></div><button className="secondary" type="button" onClick={() => setView('merge')}>Cross-cohort merge</button></section>
          {cohorts.length === 0 ? <div className="empty"><strong>No cohorts yet</strong><p>Add a workbook, clinical table, molecular file or imaging asset to begin.</p></div> : <div className="cohort-grid">{cohorts.map((cohort) => <article className="cohort-card" key={`${cohort.kind}:${cohort.name}`}><div className="card-top"><span className={`kind ${cohort.kind}`}>{cohort.kind === 'merged' ? 'Cross-cohort view' : 'Cohort'}</span><span>{cohort.file_count} files</span></div><h3>{cohort.name}</h3>{cohort.kind === 'merged' && <p className="sources">{cohort.source_cohorts.join(' + ')}</p>}<div className="format-list">{cohort.formats.slice(0, 6).map((format) => <span key={format}>{format.toUpperCase()}</span>)}</div><div className="card-actions"><button type="button" onClick={() => loadWorkspace(cohort.name)}>Open workspace</button>{cohort.kind === 'source' && <button type="button" onClick={() => addToCohort(cohort.name)}>Add files</button>}</div></article>)}</div>}
        </>}

        {view === 'add' && <section className="panel narrow"><div className="section-head"><div><p className="eyebrow">Data intake</p><h1>Add data</h1><p>Create a cohort or append new modalities/files to an existing cohort.</p></div></div><div className="tabs"><button type="button" className={intakeMode === 'files' ? 'active' : ''} onClick={() => setIntakeMode('files')}>Files</button><button type="button" className={intakeMode === 'url' ? 'active' : ''} onClick={() => setIntakeMode('url')}>External URL / API</button></div>{intakeMode === 'files' ? <form onSubmit={submitFiles}><label className="field"><span>Cohort name</span><input list="cohort-options" value={projectName} onChange={(e) => setProjectName(e.target.value)} placeholder="e.g. NEURO1-COHORT" /><datalist id="cohort-options">{sourceCohorts.map((c) => <option value={c.name} key={c.name} />)}</datalist><small>Use the same cohort name to add clinical, survival, RNA-seq, variants, sequences or images later.</small></label><label className={`dropzone ${dragActive ? 'drag-active' : ''}`} onDragEnter={(e) => { e.preventDefault(); setDragActive(true) }} onDragOver={(e) => { e.preventDefault(); setDragActive(true) }} onDragLeave={(e) => { if (e.currentTarget === e.target) setDragActive(false) }} onDrop={handleDrop}><input type="file" multiple onChange={(e) => appendFiles(Array.from(e.target.files || []))} /><span className="drop-icon">⇩</span><strong>{dragActive ? 'Drop files here' : 'Drag & drop files here'}</strong><span>or click to browse · XLSX, CSV, TSV, JSON, FASTA/FASTQ, VCF/MAF, BAM/CRAM, images, DICOM, Parquet and more.</span></label>{files.length > 0 && <div className="selected">{files.map((file) => { const key = `${file.name}:${file.size}`; return <div key={key}><span><b>{prettyType(file.name)}</b>{file.name}</span><em>{progress[key] !== undefined ? `${progress[key]}%` : formatBytes(file.size)}</em></div> })}</div>}<button className="primary full" disabled={busy} type="submit">{busy ? 'Uploading…' : 'Upload to cohort'}</button></form> : <form onSubmit={submitUrl}><label className="field"><span>Cohort name</span><input list="cohort-options-url" value={projectName} onChange={(e) => setProjectName(e.target.value)} /><datalist id="cohort-options-url">{sourceCohorts.map((c) => <option value={c.name} key={c.name} />)}</datalist></label><label className="field"><span>External URL or GET API</span><input type="url" value={externalUrl} onChange={(e) => setExternalUrl(e.target.value)} placeholder="https://example.org/cohort.json" required /></label><div className="two"><label className="field"><span>Filename override</span><input value={externalFilename} onChange={(e) => setExternalFilename(e.target.value)} placeholder="optional" /></label><label className="field"><span>Bearer token</span><input type="password" value={bearerToken} onChange={(e) => setBearerToken(e.target.value)} placeholder="optional; not stored" /></label></div><button className="primary full" disabled={busy} type="submit">{busy ? 'Importing…' : 'Import into cohort'}</button></form>}</section>}

        {view === 'workspace' && selectedCohort && <>
          <section className="workspace-hero"><div><button className="back-link" onClick={() => setView('cohorts')}>← All cohorts</button><p className="eyebrow">Cohort workspace</p><h1>{selectedCohort}</h1><div className="workspace-meta"><span>{cohortFiles.length} files</span><span>{formats.length} modalities/types</span><span>{totalTables || '—'} profiled tables</span><span>{workspaceRecords.length} saved decisions</span></div></div><button className="secondary" type="button" onClick={() => addToCohort(selectedCohort)}>+ Add files</button></section>
          <nav className="workspace-tabs">{workspaceTabs.map((tab) => <button key={tab} className={workspaceTab === tab ? 'active' : ''} onClick={() => setWorkspaceTab(tab)}>{tab[0].toUpperCase() + tab.slice(1)}</button>)}</nav>

          {workspaceTab === 'files' && <section className="panel"><div className="section-head"><div><h2>Cohort files</h2><p>Every source asset stays linked to this cohort and keeps its original provenance.</p></div><button className="secondary" onClick={() => addToCohort(selectedCohort)}>Add more files</button></div><label className={`workspace-drop ${workspaceDragActive ? 'drag-active' : ''}`} onDragEnter={(e) => { e.preventDefault(); setWorkspaceDragActive(true) }} onDragOver={(e) => { e.preventDefault(); setWorkspaceDragActive(true) }} onDragLeave={(e) => { if (e.currentTarget === e.target) setWorkspaceDragActive(false) }} onDrop={(e) => { e.preventDefault(); void uploadFilesToWorkspace(Array.from(e.dataTransfer.files || [])) }}><input type="file" multiple onChange={(e) => void uploadFilesToWorkspace(Array.from(e.target.files || []))} /><strong>{workspaceDragActive ? 'Drop to add to this cohort' : 'Drag & drop additional cohort files'}</strong><span>Drop files anywhere in this box, or click to browse. Existing source files are never overwritten.</span></label><div className="asset-grid">{cohortFiles.map((dataset) => <article className="asset-card" key={dataset.id}><div className="asset-icon">{prettyType(dataset.original_name).slice(0, 4)}</div><div className="asset-body"><strong>{dataset.original_name}</strong><span>{prettyType(dataset.original_name)} · {formatBytes(dataset.size_bytes)}</span><small>Added {new Date(dataset.created_at).toLocaleString()}</small></div><div className="asset-actions"><button onClick={() => inspectDataset(dataset, 'inspect')}>Inspect</button><button onClick={() => inspectDataset(dataset, 'harmonize')}>Harmonize</button><button onClick={() => download(dataset)}>Download</button><button type="button" className="danger-link asset-delete" disabled={busy} onClick={() => void requestDeleteDataset(dataset)}>Delete</button></div></article>)}</div></section>}

          {workspaceTab === 'inspect' && <div className="workspace-split"><section className="panel"><h2>Select or drop a file</h2><p>Choose an existing cohort asset, or drop a new local file below to add it and inspect it immediately.</p><label className={`inspect-drop ${workspaceDragActive ? 'drag-active' : ''}`} onDragEnter={(e) => { e.preventDefault(); setWorkspaceDragActive(true) }} onDragOver={(e) => { e.preventDefault(); setWorkspaceDragActive(true) }} onDragLeave={(e) => { if (e.currentTarget === e.target) setWorkspaceDragActive(false) }} onDrop={(e) => { e.preventDefault(); void uploadFilesToWorkspace(Array.from(e.dataTransfer.files || []), true) }}><input type="file" multiple onChange={(e) => void uploadFilesToWorkspace(Array.from(e.target.files || []), true)} /><strong>Drop file(s) to inspect</strong><span>Uploads into {selectedCohort} and opens the newest file.</span></label><div className="file-list">{cohortFiles.map((dataset) => <button type="button" className={selectedDatasetId === dataset.id ? 'selected-file' : ''} key={dataset.id} onClick={() => inspectDataset(dataset)}><span className="file-type">{prettyType(dataset.original_name)}</span><span><strong>{dataset.original_name}</strong><small>{formatBytes(dataset.size_bytes)}</small></span><em>{profilingId === dataset.id ? 'Inspecting…' : 'Open'}</em></button>)}</div></section><section className="panel profile-panel">{!selectedProfile ? <div className="empty compact"><strong>Select a file</strong><p>Structured files show table/sheet inventory and previews; large molecular/imaging assets retain metadata and provenance.</p></div> : <ProfileView profile={selectedProfile} />}</section></div>}

          {workspaceTab === 'harmonize' && <section className="panel harmonize-panel">
            <div className="section-head">
              <div><h2>Harmonize schema</h2><p>AI-assisted proposals remain fully reviewable: propose → visually review → drag/edit → validate → confirm → provenance.</p></div>
              <select className="compact-select" value={selectedDatasetId || ''} onChange={(e) => { const ds = cohortFiles.find((d) => d.id === Number(e.target.value)); if (ds) void inspectDataset(ds, 'harmonize') }}><option value="">Choose file</option>{cohortFiles.map((d) => <option key={d.id} value={d.id}>{d.original_name}</option>)}</select>
            </div>
            <div className="workflow-steps" aria-label="Harmonization workflow"><span className="done"><b>1</b>AI proposes</span><span><b>2</b>Review</span><span><b>3</b>Drag / edit</span><span><b>4</b>Validate</span><span><b>5</b>Confirm + provenance</span></div>
            {selectedDataset && !selectedProfile && <button className="primary" onClick={() => void inspectDataset(selectedDataset, 'harmonize')}>Profile file first</button>}
            {selectedProfile && <>
              {selectedTables.length > 1 && <label className="field table-picker"><span>Sheet / table to harmonize</span><select value={selectedTable} onChange={(e) => { setSelectedTable(e.target.value); generateMappingSuggestions(e.target.value) }}>{selectedTables.map((table) => <option key={table.name} value={table.name}>{table.name} · {table.role} · {table.rows.toLocaleString()} rows</option>)}</select></label>}
              <div className="harmonize-toolbar"><div><strong>{selectedFields.length} source fields</strong><span>{mappings.filter((m) => m.status === 'accept').length} accepted · {mappings.filter((m) => m.status === 'review').length} review · {mappings.filter((m) => m.status === 'reject').length} rejected</span></div><button type="button" className="secondary" onClick={() => generateMappingSuggestions()}>Regenerate proposals</button></div>
              <div className="mapping-board">
                <div className="mapping-column"><div className="mapping-column-head"><div><span className="eyebrow">Source</span><h3>Fields from {selectedTable || selectedDataset?.original_name || 'selected dataset'}</h3></div><small>Drag using ⠿ or use the selector below.</small></div><div className="field-card-list">{selectedFields.map((field) => { const row = mappings.find((m) => m.source === field.name); return <article className={`source-field-card ${draggedSourceField === field.name ? 'dragging' : ''}`} draggable key={field.name} onDragStart={(e) => { e.dataTransfer.setData('text/pedsonco-source-field', field.name); setDraggedSourceField(field.name) }} onDragEnd={() => setDraggedSourceField('')}><span className="drag-handle" aria-hidden="true">⠿</span><div><strong>{field.name}</strong><small>{field.inferred_type}{field.sample_values?.length ? ` · e.g. ${field.sample_values.slice(0, 2).join(', ')}` : ''}</small></div><span className={`map-badge ${row?.status || 'review'}`}>{row?.canonical || 'Unmapped'}</span></article> })}</div></div>
                <div className="mapping-column"><div className="mapping-column-head"><div><span className="eyebrow">Target</span><h3>CCDI-oriented canonical fields</h3></div><small>Drop a source field onto a target.</small></div><div className="canonical-grid">{CANONICAL_CATALOG.map((target) => { const linked = mappings.filter((m) => m.canonical === target.name && m.status !== 'reject'); return <article className="canonical-target" key={target.name} onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add('drag-over') }} onDragLeave={(e) => e.currentTarget.classList.remove('drag-over')} onDrop={(e) => { e.preventDefault(); e.currentTarget.classList.remove('drag-over'); const source = e.dataTransfer.getData('text/pedsonco-source-field'); if (source) mapSourceToCanonical(source, target.name) }}><div><strong>{target.label}</strong><code>{target.name}</code></div><span>{target.group} · {target.type}</span>{linked.length > 0 && <small>{linked.map((m) => m.source).join(', ')}</small>}</article> })}</div></div>
              </div>
              {mappings.length > 0 && <><div className="review-head"><div><h3>Review mapping decisions</h3><p>Manual edits override proposals. Dragging changes a mapping back to Review until you explicitly accept it.</p></div></div><div className="mapping-table detailed"><div className="mapping-row heading"><span>Source field</span><span>Canonical target</span><span>Proposal</span><span>Decision</span></div>{mappings.map((row, index) => <div className={`mapping-row ${mappingValidation?.issues.some((i) => i.field === row.source && i.level === 'error') ? 'has-error' : ''}`} key={`${row.source}-${index}`}><div><strong>{row.source}</strong><small>{selectedFields.find((f) => f.name === row.source)?.inferred_type || 'unknown'}</small></div><div><input list="canonical-field-options" value={row.canonical} onChange={(e) => { setMappings((current) => current.map((item, i) => i === index ? { ...item, canonical: e.target.value, status: 'review', reason: 'Manually edited by reviewer' } : item)); setMappingValidation(null) }} /><datalist id="canonical-field-options">{CANONICAL_CATALOG.map((field) => <option key={field.name} value={field.name}>{field.label}</option>)}</datalist></div><div><span className={`confidence ${row.confidence >= 90 ? 'high' : ''}`}>{row.confidence}%</span><small>{row.reason}</small></div><select value={row.status} onChange={(e) => { setMappings((current) => current.map((item, i) => i === index ? { ...item, status: e.target.value as MappingRow['status'] } : item)); setMappingValidation(null) }}><option value="accept">Accept</option><option value="review">Review</option><option value="reject">Reject</option></select></div>)}</div>
              {mappingValidation && <ValidationPanel title="System validation" valid={mappingValidation.valid} score={mappingValidation.score} issues={mappingValidation.issues} />}
              <div className="action-strip"><span>Nothing is written to the working layer until validation passes and you confirm.</span><button className="primary" disabled={busy || mappings.length === 0} onClick={() => void validateAndSaveHarmonization()}>{busy ? 'Validating…' : 'Validate & continue'}</button></div></>}
            </>}
          </section>}

          {workspaceTab === 'edit' && <div className="workspace-split"><section className="panel"><h2>Non-destructive edit recipe</h2><p>Select the exact table and field you want to edit. Dragging is intentionally not used here because field editing is clearer and safer with explicit selection. The original source object is never overwritten.</p><form onSubmit={saveEdit}><label className="field"><span>File</span><select value={selectedDatasetId || ''} onChange={(e) => { const id = Number(e.target.value); if (id) void prepareEditDataset(id); else { setSelectedDatasetId(null); setEditTable(''); setEditField('') } }}><option value="">Choose file</option>{cohortFiles.map((d) => <option key={d.id} value={d.id}>{d.original_name}</option>)}</select></label>{selectedDatasetId && !selectedProfile && <button type="button" className="secondary" onClick={() => void prepareEditDataset(selectedDatasetId)}>Load tables & fields</button>}{selectedProfile && selectedTables.length > 0 && <><label className="field"><span>Sheet / table</span><select value={editTable} onChange={(e) => { setEditTable(e.target.value); setEditField(''); setEditFieldSearch('') }}>{selectedTables.map((table) => <option key={table.name} value={table.name}>{table.name} · {table.role} · {table.rows.toLocaleString()} rows</option>)}</select><small>Choose the specific table before selecting a field. Workbook sheets remain separate linked tables.</small></label><div className="field-browser"><div className="field-browser-head"><div><strong>Available fields</strong><span>{editFields.length} detected in {editTable || 'selected table'}</span></div><input value={editFieldSearch} onChange={(e) => setEditFieldSearch(e.target.value)} placeholder="Search fields…" aria-label="Search available fields" /></div>{editFields.length === 0 ? <div className="field-browser-empty">No editable fields were detected for this table. Choose another sheet/table or re-profile the file.</div> : <div className="field-browser-list">{filteredEditFields.slice(0, 120).map((field) => <button type="button" className={editField === field.name ? 'selected' : ''} key={field.name} onClick={() => setEditField(field.name)}><span><strong>{field.name}</strong><small>{field.inferred_type}{field.sample_values?.length ? ` · ${field.sample_values.slice(0, 2).join(', ')}` : ''}</small></span><em>{editField === field.name ? 'Selected' : 'Choose'}</em></button>)}</div>}</div></>}<label className="field"><span>Operation</span><select value={editOperation} onChange={(e) => setEditOperation(e.target.value)}><option>rename field</option><option>map value</option><option>convert datatype</option><option>drop field</option><option>filter rows</option><option>deduplicate</option><option>annotation</option></select></label><label className="field"><span>Target field</span><select value={editField} onChange={(e) => setEditField(e.target.value)} disabled={!editFields.length}><option value="">Choose a field</option>{editFields.map((field) => <option value={field.name} key={field.name}>{field.name} · {field.inferred_type}</option>)}</select><small>Use the searchable field browser above or this selector. No drag-and-drop is required.</small></label><label className="field"><span>New value / rule / note</span><textarea rows={4} value={editValue} onChange={(e) => setEditValue(e.target.value)} placeholder={editOperation === 'rename field' ? 'e.g. sex' : editOperation === 'map value' ? 'e.g. F → Female' : editOperation === 'convert datatype' ? 'e.g. numeric' : editOperation === 'filter rows' ? 'e.g. >= 18 or not null' : 'Describe the transformation or note'} /></label><button className="primary full" disabled={busy || !selectedDatasetId || !editField}>Review & save edit recipe</button></form></section><RecordsPanel title="Saved edit history" records={workspaceRecords.filter((r) => r.record_type === 'edit')} onDelete={removeRecord} /></div>}

          {workspaceTab === 'integrate' && <div className="workspace-split"><section className="panel"><h2>Integrate files inside this cohort</h2><p>Drag files into source slots, then drag or select join fields. The system validates key existence before confirmation.</p><div className="integration-drop-grid"><IntegrationDropSlot label="Left source" value={leftDataset} files={cohortFiles} onChange={(value) => { setLeftDataset(value); setIntegrationValidation(null); if (value) void ensureProfile(Number(value)) }} /><IntegrationDropSlot label="Right source" value={rightDataset} files={cohortFiles} onChange={(value) => { setRightDataset(value); setIntegrationValidation(null); if (value) void ensureProfile(Number(value)) }} /></div><p className="drag-help">Drag any file card below into a source slot. Click/select alternatives remain available for keyboard and mobile use.</p><div className="draggable-assets">{cohortFiles.map((d) => <button type="button" draggable key={d.id} onDragStart={(e) => e.dataTransfer.setData('text/pedsonco-dataset-id', String(d.id))}><span className="file-type">{prettyType(d.original_name)}</span><span>{d.original_name}</span></button>)}</div><form onSubmit={saveIntegration}><div className="two"><label className="field"><span>Left file/table</span><select value={leftDataset} onChange={(e) => { setLeftDataset(e.target.value); setIntegrationValidation(null); if (e.target.value) void ensureProfile(Number(e.target.value)) }}><option value="">Choose</option>{cohortFiles.map((d) => <option key={d.id} value={d.id}>{d.original_name}</option>)}</select></label><label className="field"><span>Right file/table</span><select value={rightDataset} onChange={(e) => { setRightDataset(e.target.value); setIntegrationValidation(null); if (e.target.value) void ensureProfile(Number(e.target.value)) }}><option value="">Choose</option>{cohortFiles.map((d) => <option key={d.id} value={d.id}>{d.original_name}</option>)}</select></label></div><div className="join-key-grid"><JoinKeyDrop label="Left join key" value={leftKey} fields={leftFields} transferKey="text/pedsonco-left-key" onChange={(value) => { setLeftKey(value); setIntegrationValidation(null) }} /><div className="join-arrow">↔</div><JoinKeyDrop label="Right join key" value={rightKey} fields={rightFields} transferKey="text/pedsonco-right-key" onChange={(value) => { setRightKey(value); setIntegrationValidation(null) }} /></div><label className="field"><span>Relationship</span><select value={relationship} onChange={(e) => { setRelationship(e.target.value); setIntegrationValidation(null) }}><option>1:1</option><option>1:many</option><option>many:1</option><option>many:many</option></select></label>{integrationValidation && <ValidationPanel title="Integration validation" valid={integrationValidation.valid} issues={integrationValidation.issues} />}<button className="primary full" disabled={busy}>{busy ? 'Validating…' : 'Validate & create integrated view'}</button></form></section><RecordsPanel title="Saved relationships" records={workspaceRecords.filter((r) => r.record_type === 'integration')} onDelete={removeRecord} /></div>}

          {workspaceTab === 'explore' && <section className="panel"><div className="section-head"><div><h2>Explore cohort</h2><p>Quickly understand modalities, tables and CCDI-oriented roles before analysis.</p></div><button className="secondary" disabled={busy} onClick={profileAll}>{busy ? 'Profiling…' : 'Profile all files'}</button></div><section className="stats workspace-stats"><article><span>Files</span><strong>{cohortFiles.length}</strong></article><article><span>Types</span><strong>{formats.length}</strong></article><article><span>Profiled tables</span><strong>{totalTables}</strong></article><article><span>Saved decisions</span><strong>{workspaceRecords.length}</strong></article></section><div className="explore-grid"><div><h3>File/modalities</h3><div className="bar-list">{formats.map((type) => { const count = cohortFiles.filter((f) => prettyType(f.original_name) === type).length; return <div key={type}><span>{type}</span><i><b style={{ width: `${Math.max(8, count / Math.max(1, cohortFiles.length) * 100)}%` }} /></i><strong>{count}</strong></div> })}</div></div><div><h3>Table roles</h3><div className="role-cloud">{Object.values(profiles).flatMap((p) => [...(p.profile.sheets || []), ...(p.profile.tables || [])]).reduce<Record<string, number>>((acc, item) => { acc[item.role] = (acc[item.role] || 0) + 1; return acc }, {}) && Object.entries(Object.values(profiles).flatMap((p) => [...(p.profile.sheets || []), ...(p.profile.tables || [])]).reduce<Record<string, number>>((acc, item) => { acc[item.role] = (acc[item.role] || 0) + 1; return acc }, {})).map(([role, count]) => <span key={role}>{role}<strong>{count}</strong></span>)}</div></div></div></section>}

          {workspaceTab === 'export' && <section className="panel"><div className="section-head"><div><h2>Export & provenance</h2><p>Create a reproducible manifest of source files plus human-reviewed harmonization, edits and integration decisions.</p></div></div><div className="export-grid"><article><span className="export-icon">JSON</span><h3>Workspace manifest</h3><p>Includes cohort metadata, files, checksums, mappings, edit recipes and relationships.</p><button className="primary" onClick={exportManifest}>Download manifest</button></article><article><span className="export-icon">RAW</span><h3>Source files</h3><p>Download original registered files individually. Raw objects are never altered by workspace operations.</p><div className="download-list">{cohortFiles.slice(0, 8).map((d) => <button key={d.id} onClick={() => download(d)}>{d.original_name}</button>)}</div></article></div><div className="provenance-banner"><strong>Three-layer provenance model</strong><span>Raw source → reviewed working-layer transformations → analysis-ready integrated/derived views.</span></div></section>}
        </>}

        {view === 'workspace' && !selectedCohort && <div className="empty"><strong>Choose a cohort first</strong><p>Open a cohort from the Cohorts page to enter its workspace.</p><button className="primary" onClick={() => setView('cohorts')}>View cohorts</button></div>}

        {view === 'merge' && <section className="panel narrow"><div className="section-head"><div><p className="eyebrow">Separate cross-cohort operation</p><h1>Cross-cohort merge</h1><p>Combine two or more already harmonized cohorts into a traceable logical view. This is separate from integrating files within a single cohort.</p></div></div><form onSubmit={createMerge}><label className="field"><span>Merged cohort name</span><input value={mergeName} onChange={(e) => setMergeName(e.target.value)} placeholder="e.g. Pediatric Solid Tumors Combined" /></label><fieldset><legend>Select source cohorts</legend><div className="check-grid">{sourceCohorts.map((cohort) => <label key={cohort.name}><input type="checkbox" checked={mergeSources.includes(cohort.name)} onChange={() => toggleMergeSource(cohort.name)} /><span><strong>{cohort.name}</strong><small>{cohort.file_count} files · {formatBytes(cohort.size_bytes)}</small></span></label>)}</div></fieldset><label className="field"><span>Compatibility / harmonization notes</span><textarea value={mergeNotes} onChange={(e) => setMergeNotes(e.target.value)} rows={4} placeholder="Document schema compatibility, vocabulary alignment and intended analysis…" /></label><div className="merge-note"><strong>Non-destructive cross-cohort merge</strong><span>The merged cohort is a virtual traceable view. Source cohorts and raw files remain unchanged.</span></div><button className="primary full" disabled={busy || sourceCohorts.length < 2}>Create cross-cohort view</button></form></section>}
      </main>
    </div>
    {confirmState && <ConfirmDialog state={confirmState} onCancel={() => setConfirmState(null)} onConfirm={() => void runConfirmedAction()} />}
  </div>
}


function ConfirmDialog({ state, onCancel, onConfirm }: { state: NonNullable<ConfirmState>; onCancel: () => void; onConfirm: () => void }) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={(e) => { if (e.currentTarget === e.target) onCancel() }}><section className="confirm-box" role="dialog" aria-modal="true" aria-labelledby="confirm-title"><div className={`confirm-mark ${state.tone === 'danger' ? 'danger' : ''}`}>{state.tone === 'danger' ? '!' : '✓'}</div><h2 id="confirm-title">{state.title}</h2><p className="confirm-description">{state.message}</p><div className="confirm-actions"><button type="button" className="secondary" onClick={onCancel}>Cancel</button><button type="button" className={state.tone === 'danger' ? 'danger-button' : 'primary'} onClick={onConfirm}>{state.confirmLabel || 'Confirm'}</button></div></section></div>
}

function ValidationPanel({ title, valid, score, issues }: { title: string; valid: boolean; score?: number; issues: Array<{ level: string; code: string; field?: string | null; message: string }> }) {
  return <section className={`validation-panel ${valid ? 'valid' : 'invalid'}`} aria-live="polite"><div className="validation-head"><div><span className="validation-icon">{valid ? '✓' : '!'}</span><div><strong>{title}</strong><small>{valid ? 'No blocking errors detected.' : 'Blocking issues require attention.'}</small></div></div>{score !== undefined && <b>{score}/100</b>}</div>{issues.length === 0 ? <p className="validation-empty">No warnings or errors.</p> : <ul>{issues.map((issue, index) => <li key={`${issue.code}-${issue.field || ''}-${index}`} className={issue.level === 'error' ? 'error' : 'warning'}><span>{issue.level === 'error' ? 'Error' : 'Warning'}</span><div><strong>{issue.field || issue.code}</strong><p>{issue.message}</p></div></li>)}</ul>}</section>
}

function JoinKeyDrop({ label, value, fields, transferKey, onChange }: { label: string; value: string; fields: Array<{ name: string; inferred_type: string; sample_values: string[] }>; transferKey: string; onChange: (value: string) => void }) {
  const [over, setOver] = useState(false)
  return <div className="join-key-box"><span className="join-label">{label}</span><div className={`join-drop ${over ? 'drag-active' : ''}`} onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)} onDrop={(e) => { e.preventDefault(); setOver(false); const field = e.dataTransfer.getData(transferKey) || e.dataTransfer.getData('text/pedsonco-join-field'); if (field) onChange(field) }}><strong>{value || 'Drop a field here'}</strong><small>{value ? fields.find((field) => field.name === value)?.inferred_type || 'field' : 'Drag a field chip below or select one.'}</small></div><select value={value} onChange={(e) => onChange(e.target.value)}><option value="">Choose join key</option>{fields.map((field) => <option value={field.name} key={field.name}>{field.name} · {field.inferred_type}</option>)}</select><div className="join-field-tray">{fields.slice(0, 30).map((field) => <button type="button" draggable key={field.name} onDragStart={(e) => { e.dataTransfer.setData(transferKey, field.name); e.dataTransfer.setData('text/pedsonco-join-field', field.name) }} onClick={() => onChange(field.name)}><b>⠿</b>{field.name}</button>)}</div></div>
}

function IntegrationDropSlot({ label, value, files, onChange }: { label: string; value: string; files: Dataset[]; onChange: (value: string) => void }) {
  const selected = files.find((d) => String(d.id) === value)
  const [over, setOver] = useState(false)
  return <div className={`integration-slot ${over ? 'drag-active' : ''}`} onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)} onDrop={(e) => { e.preventDefault(); setOver(false); const id = e.dataTransfer.getData('text/pedsonco-dataset-id'); if (files.some((d) => String(d.id) === id)) onChange(id) }}><span>{label}</span><strong>{selected ? selected.original_name : 'Drop a cohort file here'}</strong><small>{selected ? `${prettyType(selected.original_name)} · ${formatBytes(selected.size_bytes)}` : 'Drag a file card below, or choose from the selector.'}</small>{selected && <button type="button" className="clear-slot" onClick={() => onChange('')}>Clear</button>}</div>
}

function RecordsPanel({ title, records, onDelete }: { title: string; records: WorkspaceRecord[]; onDelete: (id: number) => void }) {
  return <section className="panel"><h2>{title}</h2>{records.length === 0 ? <div className="empty compact"><strong>Nothing saved yet</strong><p>Your reviewed decisions will appear here with provenance.</p></div> : <div className="record-list">{records.map((record) => <article key={record.id}><div><strong>{record.name}</strong><small>{new Date(record.created_at).toLocaleString()}</small></div><button className="danger-link" onClick={() => onDelete(record.id)}>Remove</button></article>)}</div>}</section>
}

function ProfileView({ profile }: { profile: DatasetProfile }) {
  const sheets = profile.profile.sheets || profile.profile.tables || []
  return <div><div className="profile-head"><div><span className="kind source">{profile.format_name.replace('_', ' ')}</span><h2>{profile.profile.filename}</h2><p>{profile.profile.message}</p></div><strong>{profile.table_count} {profile.table_count === 1 ? 'table' : 'tables'}</strong></div>{sheets.length > 0 && <div className="sheet-list"><div className="sheet-row heading"><span>Sheet / table</span><span>Role</span><span>Rows</span><span>Columns</span></div>{sheets.map((sheet) => <div className="sheet-row" key={sheet.name}><span><strong>{sheet.name}</strong>{'empty' in sheet && sheet.empty ? <small>empty / headers only</small> : null}</span><span><i className="role-dot" />{sheet.role}</span><span>{sheet.rows.toLocaleString()}</span><span>{sheet.columns}</span></div>)}</div>}{profile.profile.paths && <div className="path-box"><strong>Detected JSON paths</strong><div>{profile.profile.paths.slice(0, 40).map((path) => <code key={path}>{path}</code>)}</div></div>}<div className="harmonize-callout"><strong>Next: harmonize this source</strong><span>Map source fields to canonical CCDI-oriented fields, review each mapping, then save an immutable provenance decision.</span></div></div>
}
