# PedsOnco AI synthetic multimodal demo cohorts

These files are synthetic and contain **no patient data**. They are intended to test the PedsOnco AI upload, registry, future parsing, harmonization, and cohort-linkage workflows.

Each cohort includes:
- `clinical.csv` — participant-level clinical data
- `specimens.tsv` — participant → specimen → assay linkage
- `clinical_nested.json` — nested JSON metadata
- `expression_counts.tsv` — small RNA-expression/count matrix
- `target_sequence.fasta` — FASTA sequence
- `example_reads.fastq` — tiny FASTQ format example
- `variants.vcf` — VCF variant example
- `variants.maf` — MAF mutation table
- `pathology_preview.png` — synthetic image preview (not diagnostic)
- `image_manifest.json` — image/sample linkage metadata
- `cohort_manifest.csv` — file inventory

## How to test
Choose one cohort folder, enter the matching cohort name in the web app, then select several files at once and upload them. The updated frontend supports multi-file registration.

## Production note
Real FASTQ, BAM, CRAM, DICOM, and whole-slide pathology files can be very large. For production, use direct MinIO/S3 uploads or file manifests rather than sending multi-gigabyte objects through a normal browser form.
