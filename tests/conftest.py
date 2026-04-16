import pytest

@pytest.fixture
def mock_napta_time_entries():
    """Générateur de mock pour les saisies de temps (Time Entries) Napta."""
    return [
        {
            "id": "te-1",
            "user_id": "u-100",
            "project_id": "p-1",
            "assignment_id": "a-1",
            "date": "2026-04-01",
            "approval_status": "approved",
            "duration": 1.0,
            "starts_at_midday": False,
            "ends_at_midday": False
        },
        {
            # Should be ignored (unapproved)
            "id": "te-2",
            "user_id": "u-100",
            "project_id": "p-1",
            "assignment_id": "a-1",
            "date": "2026-04-02",
            "approval_status": "pending",
            "duration": 1.0,
            "starts_at_midday": False,
            "ends_at_midday": False
        },
        {
            # Half-day logic test
            "id": "te-3",
            "user_id": "u-200",
            "project_id": "p-2",
            "assignment_id": "a-2",
            "date": "2026-04-03",
            "approval_status": "approved",
            "duration": 0.5,
            "starts_at_midday": True,
            "ends_at_midday": False
        }
    ]

@pytest.fixture
def mock_napta_assignments():
    """Générateur de mock pour les assignations (qui portent le TJM) Napta."""
    return [
        {
            "id": "a-1",
            "project_id": "p-1",
            "user_id": "u-100",
            "daily_fee_info": {"amount": 800.0, "currency": "EUR"},
            # Assumption: mapped sellsy info somewhere in custom fields or project info
            "custom_fields": {"sellsy_company_id": 100}
        },
        {
            "id": "a-2",
            "project_id": "p-2",
            "user_id": "u-200",
            "daily_fee_info": {"amount": 1000.0, "currency": "EUR"},
            "custom_fields": {"sellsy_company_id": 200}
        }
    ]
