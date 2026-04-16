import requests
from requests.exceptions import ConnectionError, Timeout
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, retry_if_exception

from core.logger import app_logger

def should_retry_request(exception):
    """
    Fonction de conditionnement pour Tenacity.
    On retry si c'est une Timeout, Err Connection, ou Code 429 Too Many Requests.
    """
    if isinstance(exception, (Timeout, ConnectionError)):
        return True
    if isinstance(exception, requests.HTTPError):
        # Retry only on generic 5xx server errors or 429 Rate Limiting
        return exception.response.status_code in {429, 500, 502, 503, 504}
    return False

def http_retry_decorator(max_attempts=5, min_wait=1, max_wait=30):
    """
    Exponential Backoff décorateur conçu pour respecter les contraintes Napta de Rate Limiting.
    (100 req/10s -> max 5 retries doublant le temps d'attente à chaque fois)
    """
    return retry(
        retry=retry_if_exception(should_retry_request),
        wait=wait_exponential(multiplier=min_wait, min=min_wait, max=max_wait),
        stop=stop_after_attempt(max_attempts),
        before_sleep=lambda retry_state: app_logger.warning(
            f"Retrying API call after failure '{retry_state.outcome.exception()}' "
            f"(Attempt {retry_state.attempt_number}/{max_attempts})..."
        )
    )
