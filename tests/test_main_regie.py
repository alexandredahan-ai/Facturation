import pytest
from main_regie import correlate_tjm

def test_correlate_tjm_logic():
    # Données mock simulées
    mock_assignments = [
        {
            "id": 100,
            "project_id": 999,
            "daily_fee_info": {"amount": 500.0},
            "custom_fields": {"sellsy_company_id": 12345}
        },
        {
            "id": 200,
            "project_id": 888,
            "daily_fee_info": {"amount": 600.0},
            "custom_fields": {"sellsy_company_id": "54321"} # Test string casting
        },
        {
            "id": 300, # Client invalide
            "project_id": 777,
            "daily_fee_info": {"amount": 700.0},
            "custom_fields": {}
        }
    ]

    mock_time_entries = [
        # Valide (500€ x 1)
        {"id": 1, "assignment_id": 100, "duration": 1.0, "approval_status": "approved"},
        # Valide Demi journée (600€ x 0.5)
        {"id": 2, "assignment_id": 200, "duration": 1.0, "starts_at_midday": True, "approval_status": "approved"},
        # Ignoré : pending
        {"id": 3, "assignment_id": 100, "duration": 1.0, "approval_status": "pending"},
        # Ignoré : pas de TJM link (client invalid)
        {"id": 4, "assignment_id": 300, "duration": 1.0, "approval_status": "approved"},
        # Ignoré : pas de assignation mappée
        {"id": 5, "assignment_id": 999, "duration": 1.0, "approval_status": "approved"}
    ]

    sellsy_payloads = correlate_tjm(mock_time_entries, mock_assignments)

    # 12345: 1 ligne (500)
    assert 12345 in sellsy_payloads
    assert len(sellsy_payloads[12345]) == 1
    assert sellsy_payloads[12345][0]["amount"] == 500.0

    # 54321: 1 ligne (300) car demi-journée
    assert 54321 in sellsy_payloads
    assert len(sellsy_payloads[54321]) == 1
    assert sellsy_payloads[54321][0]["amount"] == 300.0

    # Clés inexistantes ou ignorées
    for k in sellsy_payloads.keys():
        assert k in [12345, 54321]

