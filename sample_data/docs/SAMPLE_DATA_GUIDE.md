# Sample cohort data guide

Use the synthetic folders in `sample_data/` to test one cohort at a time. No file contains real patient data.

## Recommended upload sequence per cohort

1. `clinical.csv` — participant-level demographics, diagnosis, outcome
2. `specimens.tsv` — participant-to-specimen and assay linkage
3. `clinical_nested.json` — nested metadata/JSON ingestion example
4. `expression_counts.tsv` — small expression matrix
5. `target_sequence.fasta` — sequence example
6. `example_reads.fastq` — tiny raw-read example
7. `variants.vcf` and/or `variants.maf` — variant/mutation examples
8. `pathology_preview.png` + `image_manifest.json` — image + linkage metadata
9. `cohort_manifest.csv` — complete cohort file inventory

## Good production file types to support

- Clinical/metadata: CSV, TSV, XLSX, JSON, NDJSON
- Biospecimen/assays: CSV, TSV, JSON
- Sequence: FASTA, FASTQ, FASTQ.GZ
- Genomics: VCF, VCF.GZ, MAF, BED, GTF/GFF (later)
- Alignment: BAM, CRAM (register first; parse/QC asynchronously)
- Expression/omics: CSV, TSV, Parquet, H5AD (later)
- Imaging: PNG, JPG, TIFF, DICOM
- Whole-slide pathology: SVS, OME-TIFF (later viewer/tiling service)
- Reports/manifests: JSON, CSV, TXT, HTML/PDF QC reports

## Important architecture rule

Small files can be uploaded through the browser. Large FASTQ/BAM/CRAM/DICOM/WSI objects should eventually use direct MinIO/S3 upload or pre-signed URLs so the web API does not become a bottleneck.
