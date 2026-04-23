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
    # Agrégé : 1 ligne (1.0 jour à 800€/j)
    acme_items = result["Acme Corp"]
    assert len(acme_items) == 1
    assert acme_items[0]["amount"] == 800.0  # TJM
    assert acme_items[0]["quantity"] == 1.0  # total jours

    # Globex Inc : 2 demi-journées validées → agrégées en 1 ligne (1.0 jour à 1000€/j)
    globex_items = result["Globex Inc"]
    assert len(globex_items) == 1
    assert globex_items[0]["amount"] == 1000.0  # TJM
    assert globex_items[0]["quantity"] == 1.0  # 0.5 + 0.5

    # Pas de client pour le projet orphelin (999) car pas d'assignment
    # L'entry user 300 / project 999 est validée mais ignorée (pas de TJM)
    assert len(result) == 2

