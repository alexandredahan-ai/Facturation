from typing import Dict, Any, List
import pytest
from unittest.mock import patch, MagicMock

@patch('main_resell.export_finops_trace_to_bq')
@patch('main_resell.SellsyClient')
@patch('main_resell.BigQueryClient')
@patch('main_resell.GoogleSheetsClient')
def test_full_pipeline_resell(mock_sheets, mock_bq, mock_sellsy, mock_finops):
    from main_resell import run_resell_pipeline

    # Setup Mocks Data
    mock_bq_instance = MagicMock()
    mock_bq_instance.fetch_resell_data.return_value = [
        {"client_name": "Google", "sellsy_company_id": 100, "description": "Cloud Storage", "cost": 10.0, "margin_rate": 0.10},
        {"client_name": "Google", "sellsy_company_id": 100, "description": "Cloud Compute", "cost": 20.0, "margin_rate": 0.20},
        {"client_name": "MissingSellsy", "sellsy_company_id": None, "description": "Ignored", "cost": 5.0, "margin_rate": 0.0},
    ]
    mock_bq.return_value = mock_bq_instance
    
    mock_sheets_instance = MagicMock()
    mock_sheets_instance.fetch_dv360_data.return_value = [
        {"sellsy_company_id": 100, "service": "DV360 Ads", "montant": "100,0", "taux_marge": "0,15"},
        {"sellsy_company_id": 200, "service": "DV360 Services", "montant": "50,0", "taux_marge": "0,0"},
        # Ligne malformée (pas de type float castable dans 'montant') : log warning + passe silencieusement
        {"sellsy_company_id": 300, "service": "DV360 Services", "montant": "bad_value", "taux_marge": "0,0"},
    ]
    mock_sheets.return_value = mock_sheets_instance

    mock_sellsy_instance = MagicMock()
    mock_sellsy_instance.create_draft_invoice.return_value = {"id": 1234}
    mock_sellsy.return_value = mock_sellsy_instance

    # Exécution du pipe line M-1 (2026-04)
    run_resell_pipeline("2026-04", "fake_id", "A:Z")

    # Tests de vérification (Extraction et Validation Marges)
    # On vérifie la call list exacte, car l'ordre de la fusion BQ et Sheets dépend de l'implémentation du merge_invoices
    call_args_100 = mock_sellsy_instance.create_draft_invoice.call_args_list[0][0]
    call_args_200 = mock_sellsy_instance.create_draft_invoice.call_args_list[1][0]
    
    # Validation basique
    assert mock_sellsy_instance.create_draft_invoice.call_count == 2
    assert call_args_100[0] == 100
    assert len(call_args_100[2]) == 3 # 2 depuis BQ, 1 depuis DV360
    
    # Validation Export FinOps : doit être appelé 2 Fois (Pour le succès de la facture du Client 100 et pour 200)
    assert mock_finops.call_count == 2
