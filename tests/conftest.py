import pytest


# ---------------------------------------------------------------------------
# T012 — Mock JSON data generators Napta Integration API v0
# Structure fidèle à la doc officielle.
# Couvre : Time Entries, Assignments, Projects, Pagination, edge cases (FR-002/FR-004)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_napta_time_entries():
    """
    Mock Time Entries — structure réelle Napta API v0.
    Champs clés : date, workload, is_validated, status, user{napta_id, email}, project{napta_id}.
    """
    return [
        {
            # Jour complet validé — doit être facturé
            "date": "2026-04-01",
            "user": {"napta_id": 100, "external_id": "ext-100", "email": "alice@converteo.com"},
            "project": {"napta_id": 1, "external_id": "proj-alpha"},
            "workload": 1.0,
            "is_validated": True,
            "status": "saved",
        },
        {
            # Non validé — FR-002 : doit être ignoré
            "date": "2026-04-02",
            "user": {"napta_id": 100, "external_id": "ext-100", "email": "alice@converteo.com"},
            "project": {"napta_id": 1, "external_id": "proj-alpha"},
            "workload": 1.0,
            "is_validated": False,
            "status": "approval_pending",
        },
        {
            # Demi-journée validée — FR-004 : workload=0.5
            "date": "2026-04-03",
            "user": {"napta_id": 200, "external_id": "ext-200", "email": "bob@converteo.com"},
            "project": {"napta_id": 2, "external_id": "proj-beta"},
            "workload": 0.5,
            "is_validated": True,
            "status": "saved",
        },
        {
            # Autre demi-journée validée
            "date": "2026-04-04",
            "user": {"napta_id": 200, "external_id": "ext-200", "email": "bob@converteo.com"},
            "project": {"napta_id": 2, "external_id": "proj-beta"},
            "workload": 0.5,
            "is_validated": True,
            "status": "saved",
        },
        {
            # Statut saved mais non validé — doit être ignoré
            "date": "2026-04-05",
            "user": {"napta_id": 100, "external_id": "ext-100", "email": "alice@converteo.com"},
            "project": {"napta_id": 1, "external_id": "proj-alpha"},
            "workload": 1.0,
            "is_validated": False,
            "status": "saved",
        },
        {
            # Validé mais projet sans assignment (edge case — pas de TJM)
            "date": "2026-04-06",
            "user": {"napta_id": 300, "external_id": "ext-300", "email": "charlie@converteo.com"},
            "project": {"napta_id": 999, "external_id": "proj-orphan"},
            "workload": 1.0,
            "is_validated": True,
            "status": "saved",
        },
    ]


@pytest.fixture
def mock_napta_assignments():
    """
    Mock Assignments — structure réelle Napta API v0.
    Champs clés : id{napta_id}, user{napta_id}, project{napta_id}, periods[]{daily_fee_info}.
    """
    return [
        {
            "id": {"napta_id": 10, "external_id": "assign-10"},
            "simulated": False,
            "status": "Validated",
            "user": {"napta_id": 100, "external_id": "ext-100", "email": "alice@converteo.com"},
            "project": {"napta_id": 1, "external_id": "proj-alpha"},
            "periods": [
                {
                    "start_date": "2026-01-01",
                    "end_date": "2026-06-30",
                    "starts_at_midday": False,
                    "ends_at_midday": False,
                    "status": "Billable",
                    "workload": 120.0,
                    "daily_fee_info": {"amount": 800.0, "currency": "EUR"},
                }
            ],
        },
        {
            "id": {"napta_id": 20, "external_id": "assign-20"},
            "simulated": False,
            "status": "Validated",
            "user": {"napta_id": 200, "external_id": "ext-200", "email": "bob@converteo.com"},
            "project": {"napta_id": 2, "external_id": "proj-beta"},
            "periods": [
                {
                    "start_date": "2026-03-01",
                    "end_date": "2026-05-31",
                    "starts_at_midday": False,
                    "ends_at_midday": False,
                    "status": "Billable",
                    "workload": 40.0,
                    "daily_fee_info": {"amount": 1000.0, "currency": "EUR"},
                }
            ],
        },
    ]


@pytest.fixture
def mock_napta_projects():
    """
    Mock Projects — structure réelle Napta API v0.
    Champs clés : id{napta_id}, name, client, custom_text_fields.
    """
    return [
        {
            "id": {"napta_id": 1, "external_id": "proj-alpha"},
            "name": "Projet Alpha - Transformation Data",
            "client": "Acme Corp",
            "status": "In Progress",
            "archived": False,
            "custom_text_fields": {},
            "custom_dropdown_fields": {},
        },
        {
            "id": {"napta_id": 2, "external_id": "proj-beta"},
            "name": "Projet Beta - Audit SEO",
            "client": "Globex Inc",
            "status": "In Progress",
            "archived": False,
            "custom_text_fields": {},
            "custom_dropdown_fields": {},
        },
    ]


@pytest.fixture
def mock_napta_paginated_response():
    """Simule une réponse paginée Napta (cursor-based, pagination.has_more_available)."""
    page_1 = {
        "data": [
            {"date": "2026-04-01", "workload": 1.0, "is_validated": True, "status": "saved",
             "user": {"napta_id": 1, "email": "a@test.io"},
             "project": {"napta_id": 10}}
            for _ in range(3)
        ],
        "pagination": {"next_cursor": "cursor_page2", "total_count": 5, "has_more_available": True, "count": 3},
    }
    page_2 = {
        "data": [
            {"date": "2026-04-02", "workload": 0.5, "is_validated": True, "status": "saved",
             "user": {"napta_id": 2, "email": "b@test.io"},
             "project": {"napta_id": 20}}
            for _ in range(2)
        ],
        "pagination": {"next_cursor": None, "total_count": 5, "has_more_available": False, "count": 2},
    }
    return [page_1, page_2]
