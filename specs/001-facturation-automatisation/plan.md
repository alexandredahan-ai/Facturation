# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `google-cloud-bigquery`, `google-cloud-logging`, `requests`, `google-api-python-client` (for sheets), `tenacity` (for exponential backoff)
**Storage**: BigQuery, GCS (for logging/exporting traces)
**Testing**: `pytest`, `responses` (or similar request mocking for Napta)
**Target Platform**: GCP Cloud Run Jobs (Docker)
**Project Type**: Standalone Python Script / Pipeline
**Performance Goals**: Max 100req/10s on Napta API, process one month of data in < 15 minutes.
**Constraints**: OAuth2 Client Credentials (2h token validity), API Rate Limits.
**Scale/Scope**: Monthly billing runs for dozens of clients with hundreds of entries.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Architecture Modulaire**: Distinct modules for `napta_client.py`, `bq_client.py`, `sellsy_client.py`. No agentic frameworks in pipeline code.
- [x] **Naming Convention Bilingue**: Comments/Docstrings in French, Code Names (vars, functions) in English.
- [x] **Tests Unitaires**: Pytest strictly adopted.
- [x] **Résilience & Backoff**: Exponential backoff integrated for 429 errors.
- [x] **Observabilité**: Cloud Logging and BQ/GCS exports configured natively.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
