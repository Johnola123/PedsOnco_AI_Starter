# Milestone 1 Track 2 Submission Draft

## Proposed title
PedsOnco AI: Human-Reviewed Multimodal Harmonization and Analysis-Ready Cohort Integration for Childhood and AYA Cancer Data

## Scientific question and rationale
Pediatric and AYA cancer datasets are frequently distributed across clinical workbooks, sequencing manifests, molecular matrices, images, JSON exports, and institution-specific variable conventions. This heterogeneity creates avoidable friction before investigators can perform meaningful biological or AI/ML analyses. PedsOnco AI asks whether a reusable, human-reviewed interoperability layer can reduce that friction while preserving provenance and preparing cohorts for downstream analysis and future privacy-preserving federation.

## Significance
The proposed tool addresses a practical barrier between data availability and data usability. It is designed to help investigators inspect heterogeneous cohort resources, organize multimodal data under a common study context, preserve participant/sample/file relationships, and prepare harmonized outputs suitable for analysis or CCDI submission workflows.

## Novelty
The novelty is not a single prediction model. The contribution is a dataset-agnostic workflow that treats an oncology cohort as a linked multimodal object rather than a single flat table. Multi-sheet workbooks remain relational study containers; molecular, sequence, imaging and clinical files can be added over time; logical cohort merges preserve source provenance; and future AI-assisted semantic mappings are explicitly human-reviewed.

## Overall approach
The web application uses React/TypeScript, Nginx, Python/FastAPI, PostgreSQL, MinIO/S3 and Docker. The Milestone 1 prototype demonstrates cohort-aware intake, multi-sheet inspection, file registration, external URL/API ingestion, object-storage uploads, dataset profiling, and provenance-preserving cohort integration. Milestone 2 will add formal CCDI-model validation, semantic harmonization, richer analyses and a controlled federation pilot. Milestone 3 will complete CCDI integration, validation, scientific analyses and dissemination.

## Benefit to childhood and AYA cancer research
The system is intended to shorten the path from heterogeneous study files to analysis-ready cohorts, make data-quality and mapping decisions transparent, and support reuse across rare and ultra-rare cancers where combining compatible cohorts may be essential to obtain useful sample sizes.

## Collaboration and data-sharing commitments
The project will comply with applicable CCDI/NIH data-management and sharing expectations, use de-identified data for development/testing, maintain open-source code, and participate in required CCDI collaborative activities and workshops if selected.
