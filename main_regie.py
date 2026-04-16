import argparse
from typing import List, Dict, Any

from connectors.napta_client import NaptaClient, NaptaClientError
from connectors.sellsy_client import SellsyClient, SellsyClientError
from core.logger import app_logger, export_finops_trace_to_bq

def correlate_tjm(time_entries: List[Dict[str, Any]], assignments: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    """
    Rapproche les jours facturables (Time Entries) au Taux Journalier Moyen (Assignments).
    Regroupe par Sellsy Company ID.
    (FR-004 : traite la précision à la demi-journée)
    """
    # Construire un dictionnaire de correspondances [assignment_id] -> dict {tjm, sellsy_id}
    assignment_map = {}
    for a in assignments:
        try:
            # Récupérer l'ID Sellsy dans les champs personnalisés de Napta (FR-005 Mapping ID)
            sellsy_id = int(a.get("custom_fields", {}).get("sellsy_company_id", 0))
            if sellsy_id:
                fee_info = a.get("daily_fee_info", {})
                tjm = float(fee_info.get("amount", 0.0))
                assignment_map[a["id"]] = {"tjm": tjm, "sellsy_id": sellsy_id, "project": a.get("project_id")}
        except (ValueError, TypeError):
            continue

    sellsy_payloads = {}
    
    for te in time_entries:
        # Extraire uniquement les approuvés (par sécurité, si le tri Backend n'était pas parfait)
        if te.get("approval_status") != "approved":
            continue
            
        a_id = te.get("assignment_id")
        mapping = assignment_map.get(a_id)
        if not mapping:
            # Impossible de facturer (TJM ou ID client manquant)
            app_logger.debug(f"Facturation impossible pour Time Entry {te.get('id')}: Assignation {a_id} sans TJM ou mapping client Sellsy.")
            continue
            
        # Logique de gestion des demi-journées explicites de Napta (FR-004)
        duration_factor = 1.0
        if te.get("starts_at_midday") or te.get("ends_at_midday"):
            # Si un marqueur est vrai c'est au plus une demi-journée
            duration_factor = 0.5 
        else:
            # Respecter le payload de durée (au cas où il exite des 0.25 ou similaires)
            duration_factor = float(te.get("duration", 1.0))
            
        raw_price = mapping["tjm"] * duration_factor
        sellsy_id = mapping["sellsy_id"]
        
        item = {
            "description": f"Prestation de service - Projet {mapping['project']} ({duration_factor} Jours x {mapping['tjm']} €)",
            "amount": raw_price,
            "quantity": 1
        }
        
        if sellsy_id not in sellsy_payloads:
            sellsy_payloads[sellsy_id] = []
        sellsy_payloads[sellsy_id].append(item)
        
    return sellsy_payloads

def run_regie_pipeline(start_date: str, end_date: str, mock_mode: bool = False):
    """
    Orchestrateur principal du traitement Régie (Staffing) : 
    Extraction Napta -> Croisement TJM/Client -> Sellsy.
    Intègre un Mock Mode pour autoriser le développement sans credentials via tests structurés.
    """
    import uuid
    run_id = f"REGIE-{uuid.uuid4().hex[:8]}-{start_date}"
    app_logger.info(f"--- Démarrage Pipeline Régie (Période: {start_date} -> {end_date}) : Run {run_id} ---")
    
    time_entries = []
    assignments = []
    
    if mock_mode:
        app_logger.info("Mode MOCK activé. Utilisation des fixture Napta locales (Pas d'authentification OAuth2 requise).")
        from tests.conftest import mock_napta_time_entries, mock_napta_assignments
        time_entries = mock_napta_time_entries()
        assignments = mock_napta_assignments()
    else:
        try:
            napta_client = NaptaClient()
            time_entries = napta_client.fetch_approved_time_entries(start_date, end_date)
            assignments = napta_client.fetch_assignments(start_date, end_date)
        except Exception as e:
            app_logger.error(f"Echec critique extraction Napta: {e}")
            return
            
    app_logger.info(f"Données brutes récupérées : {len(time_entries)} Temps saisis, {len(assignments)} Assignments.")
    
    # Rapprochement
    consolidated_billing = correlate_tjm(time_entries, assignments)
    
    if not consolidated_billing:
        app_logger.warning("Aucune ligne de facturation Régie n'a pu être finalisée. Arrêt du script.")
        return
        
    # POST vers Sellsy
    sellsy_client = SellsyClient()
    success_count = 0
    fail_count = 0

    for sellsy_id, items in consolidated_billing.items():
        total_montant = sum(i["amount"] * i["quantity"] for i in items)
        try:
            # Test environments usually mock sellsy too, handle network issues gracefully
            res = sellsy_client.create_draft_invoice(sellsy_id, "Régie Staffing Napta", items)
            success_count += 1
            export_finops_trace_to_bq(run_id, "REGIE", str(res.get("id")), str(sellsy_id), "SUCCESS", total_montant)
        except SellsyClientError as se:
             fail_count += 1
             export_finops_trace_to_bq(run_id, "REGIE", "N/A", str(sellsy_id), "FAILED", total_montant, str(se))
        except Exception as e:
             fail_count += 1
             app_logger.error(f"Erreur Sellsy inattendue (Client {sellsy_id}): {e}")
             export_finops_trace_to_bq(run_id, "REGIE", "N/A", str(sellsy_id), "FAILED", total_montant, str(e))
             
    app_logger.info(f"--- Fin Pipeline Régie ({start_date}/{end_date}) ---")
    app_logger.info(f"Brouillons facturés (Régie): {success_count} (Succès) / {fail_count} (Erreurs)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")
    parser.add_argument("--mock", action="store_true", help="Utiliser les données mock Napta au lieu d'appeler l'API (Credentials bypass)")
    
    args = parser.parse_args()
    
    try:
        run_regie_pipeline(args.start, args.end, mock_mode=args.mock)
    except Exception as main_e:
        import sys
        app_logger.error(f"CRITICAL FAILURE in Regie Orchestrator: {main_e}")
        sys.exit(1)
