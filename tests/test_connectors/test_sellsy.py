import datetime
import pytest
from unittest.mock import patch
import requests

from connectors.sellsy_client import format_sellsy_payload, get_previous_month_name, SellsyClient, SellsyClientError, SellsyAuthManager
from core.config import settings

def test_get_previous_month_name():
    assert get_previous_month_name(datetime.date(2026, 1, 15)) == "Décembre 2025"
    assert get_previous_month_name(datetime.date(2026, 5, 15)) == "Avril 2026"

@patch('connectors.sellsy_client.datetime')
def test_format_sellsy_payload_complies_with_fr007(mock_datetime):
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
    
    assert payload["related"] == [{"id": 12345, "type": "company"}]
    assert payload["date"] == "2026-05-15"
    assert payload["subject"] == "Facturation GCP - Avril 2026"
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["type"] == "single"
    assert payload["rows"][0]["description"] == "Consommation Compute Engine"
    assert payload["rows"][0]["unit_amount"] == "1050.5"
    assert payload["rows"][0]["quantity"] == "1"

def _get_or_create_sandbox_client(auth_manager) -> int:
    """Find a company of type 'client' in sandbox (required for invoicing)."""
    headers = {
        "Authorization": f"Bearer {auth_manager.fetch_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    resp = requests.get(f"{settings.sellsy_api_base}/companies?limit=50", headers=headers)
    resp.raise_for_status()
    data = resp.json().get("data", [])

    # Must use a company with type=client (not prospect)
    for company in data:
        if company.get("type") == "client":
            return company["id"]
    
    # No client found — create one
    new_corp = {"name": "Test Acme Sandbox", "type": "client"}
    resp = requests.post(f"{settings.sellsy_api_base}/companies", json=new_corp, headers=headers)
    resp.raise_for_status()
    return resp.json()["id"]

@pytest.mark.integration
def test_create_draft_invoice_success():
    client = SellsyClient()
    sellsy_id = _get_or_create_sandbox_client(client.auth_manager)
    res = client.create_draft_invoice(sellsy_id, "OAUTH Sandbox test", [{"description": "Dev Sandbox", "amount": 1337}])
    
    assert "id" in res
    assert res.get("status", "draft") == "draft"

@patch('connectors.sellsy_client.send_slack_alert')
def test_create_draft_invoice_fails_on_missing_id(mock_slack):
    client = SellsyClient()
    
    with pytest.raises(SellsyClientError, match="Client Sellsy manquant"):
        client.create_draft_invoice(None, "Régie Napta", [])
    
    mock_slack.assert_called_once()

@pytest.mark.integration
@patch('connectors.sellsy_client.send_slack_alert')
def test_create_draft_invoice_alerts_on_sellsy_unknown(mock_slack):
    """Si Sellsy renvoie une erreur (ID obsolète/inconnu), on alerte en situation réelle."""
    client = SellsyClient()
    
    # 99999999 is definitely an invalid client ID — Sellsy returns 400 "la société n'existe pas"
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        client.create_draft_invoice(99999999, "GCP Resell Bad", [{"description": "Dev Sandbox", "amount": 1337}])
        
    assert exc.value.response.status_code in {400, 404}
    mock_slack.assert_called_once()
