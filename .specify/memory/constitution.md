<!-- Sync Impact Report
- Version change: Initial → 1.0.0
- Modified principles:
  - PRINCIPLE_1_NAME → Architecture Modulaire & Job Autonome
  - PRINCIPLE_2_NAME → Naming Convention Bilingue
  - PRINCIPLE_3_NAME → Tests Unitaires (Pytest)
  - PRINCIPLE_4_NAME → Résilience & Backoff (429)
  - PRINCIPLE_5_NAME → Observabilité Cloud Logging & Export BQ/GCS
- Added sections:
  - Architecture & Technologies
  - Logique d'Implémentation & Workflow (Mock Régie)
- Removed sections: N/A
- Templates requiring updates:
  - .specify/templates/plan-template.md (⚠ pending - update Testing to explicitly reference Pytest, Project Type to Cloud Run Jobs)
  - .specify/templates/spec-template.md (✅ updated)
  - .specify/templates/tasks-template.md (✅ updated)
- Follow-up TODOs: Attente des credentials Napta (API v0) pour la partie Régie.
-->
# Facturation Automatisation (Resell & Régie) Constitution

## Core Principles

### I. Architecture Modulaire & Job Autonome
Each connector must reside in its own dedicated, isolated module (`napta_client.py`, `sellsy_client.py`, `bq_client.py`, `sheets_client.py`). Orchestration is separate with one main orchestrator per job (Resell vs. Régie). Any pre-existing agentic layers (i.e. Google ADK code) MUST be removed in order to run as a standalone Python script on Cloud Run Jobs.

### II. Naming Convention Bilingue
Code and documentation MUST mix languages strictly according to this rule:
- Comments and documentations MUST be written in French.
- Variable names, functions, classes, and file names MUST be written in English.

### III. Tests Unitaires (Pytest)
Comprehensive unit testing is mandatory. Tests MUST be written using the `pytest` framework and properly validate logic independently of external APIs via mocking.

### IV. Résilience & Backoff (429)
The pipeline MUST include robust API error handling. 
- Implement Exponential Backoff retry strategies, extremely critical for HTTP 429 Too Many Requests errors (specifically Napta: 100 req/10s, 50k/day, 750k/month).
- Explicit alerts must be emitted for edge cases like unrecognized clients when pushing drafts to Sellsy.

### V. Observabilité Cloud Logging & Export
Monitoring must rely strictly on structured Cloud Logging. Data exports or reports required for FinOps trace tracking must be sent directly to BigQuery and/or Google Cloud Storage (GCS).

## Architecture & Technologies

- **Runtime**: Cloud Run Jobs, Docker.
- **Language**: Python 3.11+
- **APIs & Sources**:
  - BigQuery (GCP Billing, table `resell_converteo`)
  - Cloud Channel API
  - Google Sheets API (Sheet DV360, 22 columns)
  - API Napta v0 (OAuth2 Client Credentials, 2h token validity). Endpoints: `/time_entries`, `/assignments`, `/projects`, `/users`, `/leaves`
- **Destination**: API Sellsy (POST factures brouillon / draft invoices)

*Business logic rules (Régie)*:
- TJM (Daily Rate) is located in `assignments.daily_fee_info`.
- `time_entries` filter using `approval_status=approved` (invoice validated days only).
- `leaves` handle half-days (`starts_at_midday`, `ends_at_midday`).
- Pagination: cursor-based (limit 1-500).

## Logique d'Implémentation & Workflow

The delivery and development workflow MUST follow this sequence based on current blockers:
1. **Pipeline Resell (GCP & DV360)**: Currently unblocked. Can be developed end-to-end (BQ Extraction → Margins Calculation → Sellsy POST).
2. **Connecteur Sellsy**: Must be developed as a common component shared between both pipelines.
3. **Pipeline Régie (Napta)**: A skeleton must be built initially with mocked data adhering exactly to the API Napta v0 documentation, until the OAuth2 Napta credentials are provided. Logique métier must be validated on these mocks.

## Governance

- All Pull Requests or generated features MUST strictly abide by the English variables / French comments naming convention.
- Modifications to core dependencies or the architecture (e.g., adding a new tool outside standard python environment/GCP APIs) require an amendment to this Project Constitution.
- Missing credentials (e.g., Napta) are temporary states and must not halt progress on structural/mocking development.

**Version**: 1.0.0 | **Ratified**: 2026-04-15 | **Last Amended**: 2026-04-15
