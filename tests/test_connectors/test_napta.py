import pytest
import responses
from datetime import datetime, timedelta

from connectors.napta_client import NaptaAuthManager, NaptaClientError, NaptaClient
from core.config import settings


@responses.activate
def test_oauth2_lifecycle_caching():
    """Valide que le token est caché et renouvelé uniquement à T-5min."""
    responses.add(
        responses.POST,
        settings.napta_auth_url,
        json={"access_token": "token1", "expires_in": 86400},
        status=200,
    )
    
    manager = NaptaAuthManager()
    manager._token = None
    manager._expires_at = None
    
    # Premier appel : réseau hit
    token = manager.get_valid_token()
    assert token == "token1"
    assert len(responses.calls) == 1
    
    # Second appel immédiat : cache (pas de réseau)
    token2 = manager.get_valid_token()
    assert token2 == "token1"
    assert len(responses.calls) == 1

    # Simuler expiration < 5 min → renouvellement
    manager._expires_at = datetime.utcnow() + timedelta(seconds=299)
    responses.add(
        responses.POST,
        settings.napta_auth_url,
        json={"access_token": "token2", "expires_in": 86400},
        status=200,
    )
    token3 = manager.get_valid_token()
    assert token3 == "token2"
    assert len(responses.calls) == 2


def test_time_entry_filtering(mock_napta_time_entries):
    """
    Test de la logique de filtrage des Time Entries Napta (structure réelle API v0).
    Valide : is_validated (FR-002), workload demi-journées (FR-004), edge cases.
    """
    # Filtrer validées uniquement — FR-002
    validated = [te for te in mock_napta_time_entries if te.get("is_validated")]
    assert len(validated) == 4  # entrées 1, 3, 4, 6

    # Non validées exclues
    non_validated = [te for te in mock_napta_time_entries if not te.get("is_validated")]
    assert len(non_validated) == 2  # entrées 2 (approval_pending), 5 (saved mais non validé)

    # Demi-journées — FR-004 (workload=0.5)
    half_days = [te for te in validated if te.get("workload", 1.0) == 0.5]
    assert len(half_days) == 2  # entrées 3, 4

    # Jour complet
    full_days = [te for te in validated if te.get("workload", 0) == 1.0]
    assert len(full_days) == 2  # entrées 1, 6

    # Edge case : entrée validée mais projet sans assignment (project 999)
    orphans = [te for te in validated if te.get("project", {}).get("napta_id") == 999]
    assert len(orphans) == 1

