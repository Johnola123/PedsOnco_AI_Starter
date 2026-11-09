# File types the platform can grow to support

| Category | Examples | Typical use | Early handling |
|---|---|---|---|
| Clinical/metadata | CSV, TSV, XLSX, JSON, NDJSON | demographics, diagnosis, treatment, survival, data dictionaries | parse/profile/harmonize |
| Biospecimen | CSV, TSV, JSON | participant → specimen → assay linkage, tumor/normal status | parse/link/validate |
| Sequences | FASTA, FASTQ/FASTQ.GZ | reference/target sequences, raw sequencing reads | register + QC; parse FASTA; background processing for FASTQ |
| Variants | VCF/VCF.GZ, MAF | SNVs/indels and annotations | parse to canonical variant table |
| Alignments | BAM, CRAM | aligned reads | register + metadata/QC; process asynchronously |
| Expression | TSV, CSV, Parquet, H5AD (later) | RNA-seq counts/TPM/single-cell matrices | profile + feature generation |
| Imaging | DICOM, PNG, JPG, TIFF | radiology, pathology previews, microscopy | image metadata + object storage |
| Whole-slide imaging | SVS, TIFF/OME-TIFF | digital pathology | object storage + tile/preview service later |
| Proteomics/methylation | CSV, TSV, Parquet | derived quantitative molecular matrices | profile + harmonize |
| Reports/manifests | TXT, JSON, CSV, PDF (reports) | provenance, QC reports, file inventories | register/index metadata |

The starter currently registers any file in MinIO/S3 and stores its registry metadata in PostgreSQL. Format-specific parsing is intentionally staged as later milestones.
