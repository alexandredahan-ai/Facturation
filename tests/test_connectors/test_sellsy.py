import datetime
import pytest
import responses
from unittest.mock import patch

from connectors.sellsy_client import format_sellsy_payload, get_previous_month_name, SellsyClient, SellsyClientError
from core.config import settings

def test_get_previous_month_name():
    # Tester le passage à l'année précédente (Janvier -> Décembre de l'année n-1)
    assert get_previous_month_name(datetime.date(2026, 1, 15)) == "Décembre 2025"
    assert get_previous_month_name(datetime.date(2026, 5, 15)) == "Avril 2026"

@patch('connectors.sellsy_client.datetime')
def test_format_sellsy_payload_complies_with_fr007(mock_datetime):
    """
    Validation stricte du Requirement FR-007 :
    Invoice Date = Date d'exécution (Today)
    Subject = Mois Précédent (M-1)
    """
    mock_date = datetime.date(2026, 5, 15)
    
    class MockDate(datetime.date):
        @classmethod
        def today(cls):
            return mock_date
            
    mock_datetime.date = MockDate

    items = [
        {"description": "Consommation Compute Engine", "quantity": 1, "amount": 1050.50}
    ]
    
    payload = format_sellsy_payload(client_id=12345, pipeline_name="GCP", items=items)
    
    assert payload["client_id"] == 12345
    assert payload["date"] == "2026-05-15"  # Date = exécution
    assert payload["subject"] == "Facturation GCP - Avril 2026"  # Label = M-1 (avril pour exécution mai)
    assert len(payload["items"]) == 1
    assert payload["items"][0]["amount"] == 1050.50

@responses.activate
def test_create_draft_invoice_success():
    """Vérifier le POST réussi de création de brouillon avec le token d'auth."""
    responses.add(
        responses.POST,
        f"{settings.sellsy_api_base}/invoices",
        json={"id": 999, "status": "draft"},
        status=201
    )
    
    client = SellsyClient()
    res = client.create_draft_invoice(12345, "Régie Napta", [{"description": "Dev", "amount": 500}])
    
    assert res["id"] == 999
    assert len(responses.calls) == 1
    assert responses.calls[0].request.headers["Authorization"] == f"Bearer {settings.sellsy_api_key}"

@patch('connectors.sellsy_client.send_slack_alert')
def test_create_draft_invoice_fails_on_missing_id(mock_slack):
    """Si l'ID client mappé est None, on ne fait pas d'appel réseau et on alerter Finance."""
    client = SellsyClient()
    
    with pytest.raises(SellsyClientError, match="Client Sellsy manquant"):
        # Explicitly passing `None` to mock a missing mapping entry
        client.create_draft_invoice(None, "Régie Napta", [])
    
    mock_slack.assert_called_once()

@responses.activate
@patch('connectors.sellsy_client.send_slack_alert')
def test_create_draft_invoice_alerts_on_sellsy_unknown(mock_slack):
    """Si Sellsy renvoie 404 (ID obsolète/inconnu), on alerte Finance et on lève."""
    responses.add(
        responses.POST,
        f"{settings.sellsy_api_base}/invoices",
        json={"error": "Client not found"},
        status=404
    )
    
    client = SellsyClient()
    
    import requests
    with pytest.raises(requests.exceptions.HTTPError):
        client.create_draft_invoice(9999999, "GCP Resell", [])
        
    mock_slack.assert_called_once()
