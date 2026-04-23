---
description: "Task list template for feature implementation"
---

# Tasks: Automatisation Facturation (Resell & Régie)

**Input**: Design documents from `/specs/001-facturation-automatisation/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)

### Phase 1: Setup (Project Initialization)
*Goal: Initialize the codebase, dependencies, and core project structure.*

- [x] T001 Initialize Python environment and `requirements.txt` with `google-cloud-bigquery`, `google-cloud-logging`, `requests`, `tenacity`, `pytest`, `responses`
- [x] T002 Create the project skeleton and module structure: `connectors/`, `core/`, `utils/`, `tests/` with their appropriate `__init__.py` files
- [x] T003 Implement environment variables mapping in `core/config.py` (Napta credentials, Sellsy API key, BigQuery table configs)
- [x] T004 Implement structured Cloud Logging, Slack alerting, and BigQuery/GCS FinOps trace export logic in `core/logger.py` (Constitution Principle V compliance)
- [x] T005 Implement the `utils/resilience.py` module to handle generic retry mechanisms and 429 exponential backoffs using Tenacity

### Phase 2: Foundational (Blocking Prerequisites)
*Goal: Prepare common connectors and shared components before specific pipelines.*

- [x] T006 Implement the shared Sellsy destination payload formatting in `tests/test_connectors/test_sellsy.py` using `contracts/sellsy_draft.json`, explicitly ensuring logic for FR-007 (Invoice Date = execution date, Label/Subject = M-1)
- [x] T007 Implement the main `connectors/sellsy_client.py` responsible for generating Draft Invoices in Sellsy API and triggering alerts on unknown mapped clients

### Phase 3: User Story 1 - Automatisation de la facturation Resell
*Goal: Extract costs from GCP and DV360, calculate margins, and post Sellsy draft invoices.*

- [x] T008 [P] [US1] Implement BigQuery data extraction and client ID mapping lookup in `connectors/bq_client.py` for GCP Billing Cost Records
- [x] T009 [P] [US1] Implement Google Sheets DV360 extraction logic in `connectors/sheets_client.py`
- [x] T010 [US1] Write test cases in `tests/test_pipelines/test_resell.py` for correct margin calculation given dummy BQ and sheet results
- [x] T011 [US1] Implement the Resell orchestrator in `main_resell.py` that ties `bq_client`, `sheets_client`, margin computation, and `sellsy_client` together 

### Phase 4: User Story 2 - Automatisation de la facturation Régie / Staffing
*Goal: Extract validated time entries from Napta, correlate with TJM, and push to Sellsy.*

- [x] T012 [P] [US2] Create mock JSON data generators matching Napta's API `Time Entry` and `Assignment` entities in `tests/conftest.py`
- [x] T013 [US2] Implement the OAuth2 token lifecycle manager (singleton, expires in 24h, refreshing at T-5min) inside `connectors/napta_client.py` 
- [x] T014 [US2] Implement API consumption in `connectors/napta_client.py` with cursor pagination, rate-limit throttling (100 req/10s), batched [in] filters, and `utils/resilience.py` backoff
- [x] T015 [US2] Write unit tests in `tests/test_connectors/test_napta.py` assessing time-entry filters (`approval_status=approved`) and half-day mapping logic (`starts_at_midday`)
- [x] T016 [US2] Implement the Régie orchestrator in `main_regie.py` that processes Napta metrics and posts Draft Invoices to `sellsy_client`

### Phase 5: Polish & Cross-Cutting Concerns
*Goal: Make pipelines production-ready.*

- [x] T017 Create a unified `Dockerfile` setting up a Python 3.11 environment with conditional command execution via entrypoints
- [x] T018 Run the overall pytest suite (`pytest tests/ -v`) to ensure code compliance with Constitution guidelines (bilingue naming rules)
- [x] T019 Create the Cloud Scheduler deployment scripts (`deploy/scheduler.sh` with gcloud CLI) to orchestrate automated monthly execution triggers (FR-001)

## Dependencies & Completion Order
1. Phase 1 (Setup) must be strictly completed sequentially.
2. Phase 2 (Foundational) depends on Phase 1 core libraries.
3. Phase 3 (US1) and Phase 4 (US2) can technically be developed in parallel, but both depend heavily on completion of Phase 2 (T007 Sellsy Client).
4. Phase 5 executes lastly.

## Parallel Execution Examples
- Developer A works on T008 (`bq_client.py`) while Developer B works on T009 (`sheets_client.py`) concurrently.
- Developer A could configure test mocks (T012) while Developer B manages API Tokens (T013).

## Implementation Strategy
- **MVP Scope**: T001 through T011. Since US1 has no technical blockers (unlike US2 which lacks valid Napta credentials right now), building the Resell pipeline validates the end-to-end framework, observability, and Sellsy bridging.
- **Incremental Delivery**: Once T011 is complete and US1 works, the system is fundamentally functional. Then mock Régie logic (T012-T016).
