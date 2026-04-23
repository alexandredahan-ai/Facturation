import argparse
import csv
import os
from typing import List, Dict, Any, Tuple

from connectors.napta_client import NaptaClient, NaptaClientError
from connectors.sellsy_client import SellsyClient, SellsyClientError
from core.logger import app_logger, export_finops_trace_to_bq

MAPPING_CSV_PATH = os.path.join(os.path.dirname(__file__), "mapping_napta_sellsy.csv")


def load_client_mapping(csv_path: str = MAPPING_CSV_PATH) -> Dict[str, Dict[str, Any]]:
    """
    Charge le mapping Napta client_name → {sellsy_id, project_ids}
    depuis le CSV. Ne retient que les lignes où VALIDE = 'oui'.
    Supporte deux formats :
    - CSV complet avec sections === MAPPING PROPOSE ===
    - CSV simple (header + lignes de données)
    
    Retourne : { client_name: { "sellsy_id": int, "project_ids": [int] } }
    """
    mapping: Dict[str, Dict[str, Any]] = {}
    if not os.path.exists(csv_path):
        app_logger.warning(f"Fichier mapping introuvable : {csv_path}")
        return mapping

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        has_sections = False
        in_mapping_section = False
        for row in reader:
            if not row:
                continue
            # Détection de la section mapping (format complet)
            if row[0].startswith("=== MAPPING PROPOSE"):
                has_sections = True
                in_mapping_section = True
                continue
            if row[0].startswith("==="):
                in_mapping_section = False
                continue
            # Si format avec sections, on ne parse que dans la section mapping
            if has_sections and not in_mapping_section:
                continue
            # Header
            if row[0].strip() == "napta_client_name":
                if not has_sections:
                    in_mapping_section = True
                continue
            # Parse : napta_name;nb;sellsy_id;sellsy_name;type;score;VALIDE;project_ids
            if len(row) >= 7 and row[6].strip().lower() == "oui" and row[2].strip():
                try:
                    sellsy_id = int(row[2].strip())
                except ValueError:
                    continue
                # Colonne 8 (index 7) : project_ids séparés par |
                project_ids = []
                if len(row) >= 8 and row[7].strip():
                    for pid_str in row[7].strip().split("|"):
                        try:
                            project_ids.append(int(pid_str))
                        except ValueError:
                            continue
                mapping[row[0].strip()] = {
                    "sellsy_id": sellsy_id,
                    "project_ids": project_ids,
                }

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
        pid = (p.get("id") or {}).get("napta_id")
        if pid:
            project_map[pid] = {
                "name": p.get("name", ""),
                "client": p.get("client", ""),
                "custom_text_fields": p.get("custom_text_fields", {}),
            }

    result = {}
    for a in assignments:
        user_id = (a.get("user") or {}).get("napta_id")
        project_id = (a.get("project") or {}).get("napta_id")
        if not user_id or not project_id:
            continue

        # TJM = daily_fee_info de la dernière période (la plus récente)
        periods = a.get("periods") or []
        if not periods:
            continue
        last_period = periods[-1]
        fee_info = (last_period.get("daily_fee_info") or {})
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

    # Agrégation : clé = (client_name, project_name, user_email, tjm) → somme des jours
    aggregated: Dict[str, Dict[tuple, float]] = {}  # client → {(proj, user, tjm): total_days}

    for te in time_entries:
        # Sécurité : n'inclure que les validées (FR-002)
        if not te.get("is_validated"):
            continue

        user_id = (te.get("user") or {}).get("napta_id")
        project_id = (te.get("project") or {}).get("napta_id")
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

        user_email = (te.get("user") or {}).get("email", "?")
        project_name = mapping["project_name"]
        client_name = mapping["client_name"] or f"Client inconnu (projet {project_id})"
        tjm = mapping["tjm"]

        agg_key = (project_name, user_email, tjm)
        if client_name not in aggregated:
            aggregated[client_name] = {}
        aggregated[client_name][agg_key] = aggregated[client_name].get(agg_key, 0.0) + workload

    # Construire les lignes de facture à partir des données agrégées
    client_payloads: Dict[str, List[Dict[str, Any]]] = {}
    for client_name, agg_lines in aggregated.items():
        items = []
        for (project_name, user_email, tjm), total_days in sorted(agg_lines.items()):
            items.append({
                "description": f"{project_name} - {user_email} ({total_days}j x {tjm}€)",
                "amount": tjm,
                "quantity": total_days,
            })
        client_payloads[client_name] = items

    return client_payloads


def run_regie_pipeline(start_date: str, end_date: str, mapping_csv: str = None):
    """
    Orchestrateur Régie — Flux optimisé :
    1. Charger le CSV mapping → extraire les project_ids des clients validés
    2. GET /time_entries?date[ge]=...&date[le]=... (all, car filtre project ignoré par l'API)
    3. Filtrer côté Python → ne garder que les TEs des project_ids mappés
    4. GET /assignments?project.napta_id[in]=IDs (ciblé, ce filtre marche sur /assignments)
    5. Croisement TJM (projets connus via CSV → skip GET /projects)
    6. POST brouillons Sellsy groupés par client
    """
    import uuid
    run_id = f"REGIE-{uuid.uuid4().hex[:8]}-{start_date}"
    app_logger.info(f"--- Démarrage Pipeline Régie ({start_date} → {end_date}) : Run {run_id} ---")

    # 1. Charger le mapping CSV
    client_sellsy_map = load_client_mapping(mapping_csv) if mapping_csv else load_client_mapping()
    if not client_sellsy_map:
        app_logger.warning("Aucun mapping validé dans le CSV. Arrêt.")
        return

    # Collecter tous les project_ids des clients mappés
    all_project_ids_set: set = set()
    for client_name, info in client_sellsy_map.items():
        pids = info.get("project_ids", [])
        all_project_ids_set.update(pids)

    if not all_project_ids_set:
        app_logger.warning("Aucun project_id dans le mapping. Exécution en mode legacy (fetch all).")
        return _run_regie_pipeline_legacy(start_date, end_date, client_sellsy_map, run_id)

    app_logger.info(f"Mapping: {len(client_sellsy_map)} clients, {len(all_project_ids_set)} project_ids ciblés")

    try:
        napta = NaptaClient()

        # 2. Fetch ALL time entries de la période (le filtre project.napta_id[in] est ignoré par l'API Napta)
        all_time_entries = napta.fetch_time_entries(start_date, end_date)

        # 3. Filtrer côté Python : validées + project_ids mappés
        validated = [
            te for te in all_time_entries
            if te.get("is_validated")
            and ((te.get("project") or {}).get("napta_id")) in all_project_ids_set
        ]
        app_logger.info(f"Time entries: {len(all_time_entries)} total → {len(validated)} validées & ciblées (sur {len(all_project_ids_set)} projets)")

        if not validated:
            app_logger.warning("Aucune time entry validée pour les projets mappés. Arrêt.")
            return

        # 4. Assignments ciblés (le filtre project.napta_id[in] FONCTIONNE sur /assignments)
        target_pids = list({(te.get("project") or {}).get("napta_id") for te in validated if (te.get("project") or {}).get("napta_id")})
        assignments = napta.fetch_assignments_for_projects(target_pids)

    except NaptaClientError as e:
        app_logger.error(f"Echec extraction Napta: {e}")
        return

    # 4. Construire les project infos depuis le mapping (pas besoin de GET /projects)
    projects_from_mapping = []
    for client_name, info in client_sellsy_map.items():
        for pid in info.get("project_ids", []):
            projects_from_mapping.append({
                "id": {"napta_id": pid},
                "name": f"Projet {pid}",
                "client": client_name,
            })

    # 5. Croisement TJM
    consolidated = correlate_tjm(validated, assignments, projects_from_mapping)

    if not consolidated:
        app_logger.warning("Aucune ligne de facturation Régie finalisée. Arrêt.")
        return

    # 6. POST vers Sellsy
    sellsy_client = SellsyClient()
    success_count = 0
    fail_count = 0
    skip_count = 0

    for client_name, items in consolidated.items():
        total_montant = sum(i["amount"] for i in items)

        client_info = client_sellsy_map.get(client_name)
        if not client_info:
            app_logger.debug(f"Client '{client_name}' non mappé → ignoré ({len(items)} lignes, {total_montant:.2f}€)")
            skip_count += 1
            continue

        sellsy_id = client_info["sellsy_id"]
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


def _run_regie_pipeline_legacy(start_date: str, end_date: str, client_sellsy_map: Dict[str, Dict[str, Any]], run_id: str):
    """Fallback legacy: fetch all time entries si aucun project_id dans le mapping."""
    try:
        napta = NaptaClient()
        time_entries = napta.fetch_validated_time_entries(start_date, end_date)
        if not time_entries:
            app_logger.warning("Aucune time entry validée trouvée. Arrêt.")
            return

        project_ids = list({(te.get("project") or {}).get("napta_id") for te in time_entries if (te.get("project") or {}).get("napta_id")})
        app_logger.info(f"{len(time_entries)} time entries validées sur {len(project_ids)} projets (mode legacy).")

        assignments = napta.fetch_assignments_for_projects(project_ids)
        projects = napta.fetch_projects(project_ids)

    except NaptaClientError as e:
        app_logger.error(f"Echec extraction Napta: {e}")
        return

    consolidated = correlate_tjm(time_entries, assignments, projects)
    if not consolidated:
        app_logger.warning("Aucune ligne de facturation Régie finalisée. Arrêt.")
        return

    sellsy_client = SellsyClient()
    success_count = 0
    fail_count = 0
    skip_count = 0

    for client_name, items in consolidated.items():
        total_montant = sum(i["amount"] for i in items)
        client_info = client_sellsy_map.get(client_name)
        if not client_info:
            app_logger.debug(f"Client '{client_name}' non mappé → ignoré ({len(items)} lignes, {total_montant:.2f}€)")
            skip_count += 1
            continue

        sellsy_id = client_info["sellsy_id"]
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

    app_logger.info(f"--- Fin Pipeline Régie legacy ({start_date}/{end_date}) ---")
    app_logger.info(f"Factures créées: {success_count} / Erreurs: {fail_count} / Ignorés (non mappés): {skip_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")
    parser.add_argument("--mapping", default=None, help="Chemin vers le CSV de mapping (défaut: mapping_napta_sellsy.csv)")
    
    args = parser.parse_args()
    
    try:
        run_regie_pipeline(args.start, args.end, mapping_csv=args.mapping)
    except Exception as main_e:
        import sys, traceback
        app_logger.error(f"CRITICAL FAILURE in Regie Orchestrator: {main_e}")
        traceback.print_exc()
        sys.exit(1)
