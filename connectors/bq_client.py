from typing import List, Dict, Any
from google.cloud import bigquery

from core.config import settings
from core.logger import app_logger

class BigQueryClientError(Exception):
    """Exception custom pour le client BigQuery"""
    pass

class BigQueryClient:
    """
    Client pour requêter les données GCP Billing et les mappings.
    """
    def __init__(self):
        self.project_id = settings.gcp_project_id
        self.table_name = settings.bq_resell_table
        try:
            self.client = bigquery.Client(project=self.project_id)
        except Exception as e:
            app_logger.error(f"Erreur d'initialisation du client BigQuery: {e}")
            raise BigQueryClientError(f"Erreur init BQ: {e}")

    def fetch_resell_data(self, billing_month: str) -> List[Dict[str, Any]]:
        """
        Extrait les données de coûts Resell GCP pour un mois donné (ex: '2026-04').
        S'attend à une table contenant des colonnes comme: client_id, sellsy_id, sku_description, cost, margin_rate
        """
        app_logger.info(f"Extraction des coûts BigQuery pour le mois {billing_month}")
        
        # Exemple de requête (à adapter à la structure exacte de la table resell_converteo)
        query = f"""
            SELECT 
                client_id,
                MAX(sellsy_company_id) as sellsy_company_id,
                STRING_AGG(DISTINCT client_name) as client_name,
                sku_description as description,
                SUM(cost) as total_cost,
                MAX(margin_rate) as margin_rate
            FROM `{self.table_name}`
            WHERE FORMAT_DATE('%Y-%m', usage_date) = @billing_month
            GROUP BY client_id, sku_description
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("billing_month", "STRING", billing_month)
            ]
        )
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            
            records = []
            for row in results:
                records.append({
                    "client_id": row.client_id,
                    "sellsy_company_id": row.sellsy_company_id,
                    "client_name": row.client_name,
                    "description": row.description,
                    "cost": float(row.total_cost),
                    "margin_rate": float(row.margin_rate) if row.margin_rate else 0.0
                })
                
            app_logger.info(f"{len(records)} lignes de coûts extraites de BQ.")
            return records
            
        except Exception as e:
            msg = f"Erreur lors de l'extraction BigQuery: {str(e)}"
            app_logger.error(msg)
            raise BigQueryClientError(msg)
