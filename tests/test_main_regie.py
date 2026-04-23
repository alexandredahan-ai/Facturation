import pytest
from main_regie import correlate_tjm


def test_correlate_tjm_logic(mock_napta_time_entries, mock_napta_assignments, mock_napta_projects):
    """
    Test unitaire du croisement Time Entries × Assignments × Projects.
    Structure API réelle Napta v0.
    Vérifie : calcul TJM × workload, regroupement par client, exclusion non-validées.
    """
    result = correlate_tjm(mock_napta_time_entries, mock_napta_assignments, mock_napta_projects)

    # 2 clients attendus : "Acme Corp" (projet 1) et "Globex Inc" (projet 2)
    assert "Acme Corp" in result
    assert "Globex Inc" in result

    # Acme Corp : 1 time entry validée (user 100, project 1, workload 1.0, TJM 800€)
    acme_items = result["Acme Corp"]
    assert len(acme_items) == 1
    assert acme_items[0]["amount"] == 800.0  # 1.0 jour × 800€

    # Globex Inc : 2 demi-journées validées (user 200, project 2, workload 0.5, TJM 1000€)
    globex_items = result["Globex Inc"]
    assert len(globex_items) == 2
    assert globex_items[0]["amount"] == 500.0  # 0.5 jour × 1000€
    assert globex_items[1]["amount"] == 500.0

    # Pas de client pour le projet orphelin (999) car pas d'assignment
    # L'entry user 300 / project 999 est validée mais ignorée (pas de TJM)
    assert len(result) == 2

