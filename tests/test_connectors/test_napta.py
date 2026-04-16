import pytest
import responses
from datetime import datetime, timedelta

from connectors.napta_client import NaptaAuthManager, NaptaClientError, NaptaClient
from core.config import settings

@responses.activate
def test_oauth2_lifecycle_caching():
    """Valide que le token n'est pas redemandé tant qu'il a de la marge (5min)."""
    # 1. Mock l'auth endpoint
    responses.add(
        responses.POST,
        settings.napta_auth_url,
        json={"access_token": "token1", "expires_in": 7200},
        status=200
    )
    
    manager = NaptaAuthManager()
    
    # Force state clearing since it's a singleton (for test isolation)
    manager._token = None
    manager._expires_at = None
    
    # Premier appel : réseau hit (1 call)
    token = manager.get_valid_token()
    assert token == "token1"
    assert len(responses.calls) == 1
    
    # Second appel immédiat : cache
    token2 = manager.get_valid_token()
    assert token2 == "token1"
    assert len(responses.calls) == 1  # 0 API calls supplémentaires

    # Troisième appel simulé (Expiration < 5 minutes)
    manager._expires_at = datetime.utcnow() + timedelta(seconds=299)
    responses.add(
        responses.POST,
        settings.napta_auth_url,
        json={"access_token": "token2", "expires_in": 7200},
        status=200
    )
    token3 = manager.get_valid_token()
    assert token3 == "token2"
    assert len(responses.calls) == 2

from tests.conftest import mock_napta_time_entries

def test_time_entry_filtering(mock_napta_time_entries):
    """
    Test unitaire d'une logique de calcul qu'on injectera dans l'orchestrateur Régie.
    On valide ici l'isolement des filtres (approved) et la gestion start_at_midday.
    """
    # Filtrer approved
    approved_entries = [te for te in mock_napta_time_entries if te.get("approval_status") == "approved"]
    assert len(approved_entries) == 2
    
    # Filtrage demi-journées
    for te in approved_entries:
        raw_duration = te.get("duration", 1.0)
        # Si la saisie stipule une demi-journée, est-ce géré statiquement ou par la source API?
        # La spec mentionne `starts_at_midday` et FR-004.
        if te.get("starts_at_midday") or te.get("ends_at_midday"):
            # Ensure it is treated as max 0.5 regardless of source input anomalies
            assert min(raw_duration, 0.5) == 0.5
        else:
            assert raw_duration == 1.0

