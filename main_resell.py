import argparse
from typing import List, Dict, Any

from connectors.bq_client import BigQueryClient
from connectors.sheets_client import GoogleSheetsClient
from connectors.sellsy_client import SellsyClient, SellsyClientError
from core.logger import app_logger, export_finops_trace_to_bq

def compute_margined_costs(records: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    """
    Calcule les marges sur les coûts bruts GCP et consolide par Sellsy ID pour la facturation finale.
    Applique la formule : coût + (coût * taux de marge).
    """
    consolidated = {}
    
    for row in records:
        sellsy_id = row.get("sellsy_company_id")
        
        # Ignorer silencieusement si la donnée est inexploitable ou brouillon (GCP ID non mappé)
        if not sellsy_id:
            app_logger.warning(f"Ligne de coût ignorée car Sellsy ID manquant (Client GCP: {row.get('client_name')})")
            continue
            
        cost = float(row.get("cost", 0.0))
        margin_rate = float(row.get("margin_rate", 0.0))
        final_price = cost + (cost * margin_rate)
        
        item = {
            "description": f"Refacturation {row.get('description', 'Service Cloud')} (Marge: {margin_rate*100}%)",
            "amount": final_price,
            "quantity": 1
        }
        
        if sellsy_id not in consolidated:
            consolidated[sellsy_id] = []
        consolidated[sellsy_id].append(item)
        
    return consolidated

def process_dv360_data(records: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    """
    Formate les données DV360 issues de Sheets pour la fusion vers le même Sellsy payload.
    Hypothèse : La feuille de Clara contient "sellsy_company_id", "service", "montant" et "taux_marge".
    """
    consolidated = {}
    for row in records:
        # Nettoyage et typage lâche vu que c'est du Sheets
        try:
            sellsy_id = int(row.get("sellsy_company_id", 0))
            if not sellsy_id:
                 continue
            
            # Formule: Montant * (1 + Taux Marge) 
            raw_montant = float(str(row.get("montant", "0")).replace(',', '.'))
            raw_marge = float(str(row.get("taux_marge", "0")).replace(',', '.'))
            
            final_price = raw_montant * (1 + raw_marge)
            service_desc = row.get("service", "Achat Média DV360")
            
            item = {
                "description": f"Refacturation {service_desc} (Marge: {raw_marge*100}%)",
                "amount": final_price,
                "quantity": 1
            }
            if sellsy_id not in consolidated:
                 consolidated[sellsy_id] = []
            consolidated[sellsy_id].append(item)
        except ValueError as e:
            app_logger.warning(f"Erreur de typage en traitant la ligne DV360 {row}: {e}")
            continue
    return consolidated

def merge_invoices(bq_invoices: dict, dv360_invoices: dict) -> dict:
    """Merge les dictionnaires de facturation en cumulant les items."""
    merged = bq_invoices.copy()
    for s_id, items in dv360_invoices.items():
        if s_id in merged:
            merged[s_id].extend(items)
        else:
            merged[s_id] = items
    return merged

def run_resell_pipeline(billing_month: str, sheet_id: str, sheet_range: str):
    """
    Orchestrateur principal du traitement Resell : Extraction GCP & DV360 -> Calcul -> Sellsy
    """
    import uuid
    run_id = f"RESELL-{uuid.uuid4().hex[:8]}-{billing_month}"
    app_logger.info(f"--- Démarrage Pipeline Resell ({billing_month}) : Run {run_id} ---")
    
    # 1. Pipeline GCP (BigQuery)
    # BQ Client will throw exception immediately if project or config is invalid
    # For CI and mock runs we handle exceptions cleanly
    bq_consolidated = {}
    try:
        bq_client = BigQueryClient()
        gcp_records = bq_client.fetch_resell_data(billing_month)
        bq_consolidated = compute_margined_costs(gcp_records)
    except Exception as e:
        app_logger.error(f"GCP Extraction skipped or failed: {e}")

    # 2. Pipeline DV360 (Google Sheets)
    dv360_consolidated = {}
    try:
        sheets_client = GoogleSheetsClient(sheet_id, sheet_range)
        dv360_records = sheets_client.fetch_dv360_data()
        dv360_consolidated = process_dv360_data(dv360_records)
    except Exception as e:
         app_logger.error(f"DV360 Extraction skipped or failed: {e}")

    # 3. Consolidation et Envoi vers Sellsy
    final_invoices = merge_invoices(bq_consolidated, dv360_consolidated)
    
    if not final_invoices:
        app_logger.warning(f"Aucune ligne de facturation viable à créer pour la Resell sur {billing_month}")
        return 
        
    sellsy_client = SellsyClient()
    success_count = 0
    fail_count = 0
    
    for sellsy_id, items in final_invoices.items():
        total_montant = sum(i["amount"] * i["quantity"] for i in items)
        try:
            res = sellsy_client.create_draft_invoice(sellsy_id, "Resell (GCP/DV360)", items)
            success_count += 1
            export_finops_trace_to_bq(run_id, "RESELL", res.get("id"), str(sellsy_id), "SUCCESS", total_montant)
        except SellsyClientError as se:
            fail_count += 1
            export_finops_trace_to_bq(run_id, "RESELL", "N/A", str(sellsy_id), "FAILED", total_montant, str(se))
        except Exception as e:
            fail_count += 1
            app_logger.error(f"Erreur inattendue pour le client {sellsy_id}: {e}")
            export_finops_trace_to_bq(run_id, "RESELL", "N/A", str(sellsy_id), "FAILED", total_montant, str(e))
            
    app_logger.info(f"--- Fin Pipeline Resell ({billing_month}) ---")
    app_logger.info(f"Brouillons facturés: {success_count} (Succès) / {fail_count} (Erreurs)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True, help="Billing month in format YYYY-MM (e.g. 2026-04)")
    parser.add_argument("--sheet-id", required=False, default="dv360_test_id", help="Google Sheet ID DV360")
    parser.add_argument("--sheet-range", required=False, default="Data!A:V", help="Google Sheet Range (e.g. Data!A:V)")
    args = parser.parse_args()
    
    try:
        run_resell_pipeline(args.month, args.sheet_id, args.sheet_range)
    except Exception as main_e:
        import sys
        app_logger.error(f"CRITICAL FAILURE in Resell Orchestrator: {main_e}")
        sys.exit(1)
