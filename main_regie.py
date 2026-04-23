import argparse
import csv
import os
from typing import List, Dict, Any, Tuple

from connectors.napta_client import NaptaClient, NaptaClientError
from connectors.sellsy_client import SellsyClient, SellsyClientError
from core.logger import app_logger, export_finops_trace_to_bq

MAPPING_CSV_PATH = os.path.join(os.path.dirname(__file__), "mapping_napta_sellsy.csv")


def load_client_mapping(csv_path: str = MAPPING_CSV_PATH) -> Dict[str, int]:
    """
    Charge le mapping Napta client_name → Sellsy company_id
    depuis le CSV. Ne retient que les lignes où VALIDE = 'oui'.
    """
    mapping = {}
    if not os.path.exists(csv_path):
        app_logger.warning(f"Fichier mapping introuvable : {csv_path}")
        return mapping

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        in_mapping_section = False
        for row in reader:
            if not row:
                continue
            # Détection de la section mapping
            if row[0].startswith("=== MAPPING PROPOSE"):
                in_mapping_section = True
                continue
            if row[0].startswith("==="):
                in_mapping_section = False
                continue
            if not in_mapping_section:
                continue
            # Header
            if row[0] == "napta_client_name":
                continue
            # Parse : napta_name;nb;sellsy_id;sellsy_name;type;score;VALIDE
            if len(row) >= 7 and row[6].strip().lower() == "oui" and row[2].strip():
                try:
                    mapping[row[0].strip()] = int(row[2].strip())
                except ValueError:
                    continue

    app_logger.info(f"Mapping chargé : {len(mapping)} clients validés depuis {csv_path}")
    return mapping


def build_assignment_map(assignments: List[Dict[str, Any]], projects: List[Dict[str, Any]]) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """
    Construit un index (user_napta_id, project_napta_id) → { tjm, project_name, client_name }
    à partir des assignments et des projets Napta API v0.

    Le TJM vient de assignment.periods[].daily_fee_info.amount (dernière période).
    Le nom du client vient de project.client.
    """
    # Index projets par napta_id
    project_map = {}
    for p in projects:
        pid = p.get("id", {}).get("napta_id")
        if pid:
            project_map[pid] = {
                "name": p.get("name", ""),
                "client": p.get("client", ""),
                "custom_text_fields": p.get("custom_text_fields", {}),
            }

    result = {}
    for a in assignments:
        user_id = a.get("user", {}).get("napta_id")
        project_id = a.get("project", {}).get("napta_id")
        if not user_id or not project_id:
            continue

        # TJM = daily_fee_info de la dernière période (la plus récente)
        periods = a.get("periods", [])
        if not periods:
            continue
        last_period = periods[-1]
        fee_info = last_period.get("daily_fee_info", {})
        tjm = float(fee_info.get("amount", 0.0))
        if tjm <= 0:
            continue

        proj_info = project_map.get(project_id, {})

        result[(user_id, project_id)] = {
            "tjm": tjm,
            "project_name": proj_info.get("name", f"Projet {project_id}"),
            "client_name": proj_info.get("client", ""),
            "custom_text_fields": proj_info.get("custom_text_fields", {}),
        }

    return result


def correlate_tjm(
    time_entries: List[Dict[str, Any]],
    assignments: List[Dict[str, Any]],
    projects: List[Dict[str, Any]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Rapproche les time entries validées aux TJM des assignments.
    Regroupe par client Napta (project.client).

    Clé de jointure : (user.napta_id, project.napta_id).
    Time entry.workload = nombre de jours (float, ex: 0.5 pour une demi-journée).
    Assignment.periods[-1].daily_fee_info.amount = TJM.

    Retourne : { "Nom Client": [ {description, amount, quantity}, ... ] }
    """
    if projects is None:
        projects = []

    amap = build_assignment_map(assignments, projects)
    client_payloads: Dict[str, List[Dict[str, Any]]] = {}

    for te in time_entries:
        # Sécurité : n'inclure que les validées (FR-002)
        if not te.get("is_validated"):
            continue

        user_id = te.get("user", {}).get("napta_id")
        project_id = te.get("project", {}).get("napta_id")
        key = (user_id, project_id)

        mapping = amap.get(key)
        if not mapping:
            app_logger.debug(
                f"Pas d'assignment trouvé pour user={user_id} project={project_id}, time entry ignorée."
            )
            continue

        # workload = jours travaillés (gère nativement les demi-journées — FR-004)
        workload = float(te.get("workload", 0.0))
        if workload <= 0:
            continue

        montant = mapping["tjm"] * workload
        user_email = te.get("user", {}).get("email", "?")
        project_name = mapping["project_name"]
        client_name = mapping["client_name"] or f"Client inconnu (projet {project_id})"

        item = {
            "description": f"{project_name} - {user_email} ({workload}j x {mapping['tjm']}€)",
            "amount": montant,
            "quantity": 1,
        }

        if client_name not in client_payloads:
            client_payloads[client_name] = []
        client_payloads[client_name].append(item)

    return client_payloads


def run_regie_pipeline(start_date: str, end_date: str):
    """
    Orchestrateur Régie : Napta validated time entries → TJM × jours → brouillons Sellsy.
    
    Flux optimisé :
    1. GET /time_entries?date[ge]=...&date[le]=... (filtre serveur par période)
    2. Extraire les project IDs uniques
    3. GET /assignments?project.napta_id[in]=... (TJM)
    4. GET /projects?id.napta_id[in]=... (nom client)
    5. Croisement → brouillons Sellsy groupés par client
    """
    import uuid
    run_id = f"REGIE-{uuid.uuid4().hex[:8]}-{start_date}"
    app_logger.info(f"--- Démarrage Pipeline Régie ({start_date} → {end_date}) : Run {run_id} ---")
    
    try:
        napta = NaptaClient()
        
        # 1. Time entries validées de la période
        time_entries = napta.fetch_validated_time_entries(start_date, end_date)
        if not time_entries:
            app_logger.warning("Aucune time entry validée trouvée. Arrêt.")
            return
        
        # 2. Projets uniques impliqués
        project_ids = list({te.get("project", {}).get("napta_id") for te in time_entries if te.get("project", {}).get("napta_id")})
        app_logger.info(f"{len(time_entries)} time entries validées sur {len(project_ids)} projets.")
        
        # 3. Assignments (TJM) pour ces projets uniquement
        assignments = napta.fetch_assignments_for_projects(project_ids)
        
        # 4. Projets (nom client) pour ces projets uniquement
        projects = napta.fetch_projects(project_ids)
        
    except NaptaClientError as e:
        app_logger.error(f"Echec extraction Napta: {e}")
        return
            
    # 5. Croisement TJM
    consolidated = correlate_tjm(time_entries, assignments, projects)
    
    if not consolidated:
        app_logger.warning("Aucune ligne de facturation Régie finalisée. Arrêt.")
        return
        
    # 6. POST vers Sellsy (groupé par client, via mapping CSV)
    client_sellsy_map = load_client_mapping()
    if not client_sellsy_map:
        app_logger.warning("Aucun mapping validé dans le CSV. Aucune facture ne sera postée.")
    
    sellsy_client = SellsyClient()
    success_count = 0
    fail_count = 0
    skip_count = 0

    for client_name, items in consolidated.items():
        total_montant = sum(i["amount"] for i in items)
        
        sellsy_id = client_sellsy_map.get(client_name)
        if not sellsy_id:
            app_logger.debug(f"Client '{client_name}' non mappé → ignoré ({len(items)} lignes, {total_montant:.2f}€)")
            skip_count += 1
            continue
        
        app_logger.info(f"Client '{client_name}' → Sellsy #{sellsy_id}: {len(items)} lignes, total {total_montant:.2f}€")
        
        try:
            result = sellsy_client.create_draft_invoice(sellsy_id, "Régie", items)
            invoice_id = result.get("id", "?")
            app_logger.info(f"  ✓ Facture brouillon #{invoice_id} créée pour '{client_name}'")
            success_count += 1
            export_finops_trace_to_bq(run_id, "REGIE", "draft_created", client_name, str(sellsy_id), total_montant)
        except Exception as e:
            app_logger.error(f"  ✗ Echec facture pour '{client_name}' (Sellsy #{sellsy_id}): {e}")
            fail_count += 1
            export_finops_trace_to_bq(run_id, "REGIE", "error", client_name, str(sellsy_id), total_montant)
             
    app_logger.info(f"--- Fin Pipeline Régie ({start_date}/{end_date}) ---")
    app_logger.info(f"Factures créées: {success_count} / Erreurs: {fail_count} / Ignorés (non mappés): {skip_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    try:
        run_regie_pipeline(args.start, args.end)
    except Exception as main_e:
        import sys
        app_logger.error(f"CRITICAL FAILURE in Regie Orchestrator: {main_e}")
        sys.exit(1)
