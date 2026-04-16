# Phase 0: Research & Architecture Decisions

## Decision 1: Authentication & Token Management for Napta API
- **Context**: Napta uses OAuth2 Client Credentials with a 2-hour token validity.
- **Decision**: The `napta_client.py` will implement a singleton-like authentication session that checks token expiration before requests. If the token is within 5 minutes of expiring, it will seamlessly fetch a new one.
- **Alternatives considered**: Passing token to every function manually (rejected to avoid repeating token fetch logic).

## Decision 2: Handling Napta API Rate Limits (100 req/10s, 50k/jour)
- **Context**: Strict rate limiting applied by Napta.
- **Decision**: Use the `tenacity` library (or equivalent utility `utils/resilience.py`) to implement exponential backoff specifically tracking HTTP 429 status codes. We will also implement a proactive sleep/throttle of `0.1s` between requests to stay safely under the 100/10s limit.
- **Alternatives considered**: Just sleeping on 429 (rejected as less robust than exponential backoff).

## Decision 3: Client Mapping (Source to Sellsy)
- **Context**: We need to link entities in GCP/Napta to Sellsy records.
- **Decision**: A centralized mapping configuration or BigQuery lookup table will be queried at the start of the job. `sellsy_client.py` relies on this external ID (e.g., `sellsy_company_id`) and fails gracefully with an alert if a lookup yields no result.

## Decision 4: Logging and Alerting
- **Context**: Alerting must go to Slack/Google Chat, and logs to Cloud Logging.
- **Decision**: Centralized `core/logger.py` will configure Google Cloud Logging. Unrecognized clients will push a structured JSON log with severity WARNING/ERROR, which will be caught by a GCP Log Sink to trigger a Pub/Sub -> Cloud Function -> Slack notification (or direct webhook call if configured inside the script for simplicity).
