import json
import logging
import requests
from datetime import datetime
from google.cloud import logging as gc_logging
from google.cloud import bigquery
from .config import settings

def setup_logger(name: str):
    """
    Initialise le logger structuré Google Cloud Logging ou un logger standard local
    """
    try:
        client = gc_logging.Client(project=settings.gcp_project_id)
        client.setup_logging()
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
    except Exception as e:
        # Fallback local
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(name)
        logger.warning(f"Could not setup GC Logging: {e}")
    return logger

app_logger = setup_logger("facturation_jobs")

def send_slack_alert(message: str, details: dict = None):
    """
    Envoie une alerte Slack pour l'équipe Finance.
    """
    payload = {
        "text": f"🚨 *Alerte Facturation*\n{message}",
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"🚨 *Facturation Automatisation* : {message}"}
            }
        ]
    }
    if details:
        code_block = f"```\n{json.dumps(details, indent=2)}\n```"
        payload["blocks"].append({
             "type": "section",
             "text": {"type": "mrkdwn", "text": f"Détails :\n{code_block}"}
        })

    try:
        response = requests.post(settings.slack_webhook_url, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        app_logger.info("Sent Slack alert successfully")
    except requests.RequestException as e:
        app_logger.error(f"Failed to send Slack alert: {e}")

def export_finops_trace_to_bq(run_id: str, job_type: str, item_id: str, client_id: str, status: str, total_amount: float, message: str = ""):
    """
    Exporte une trace détaillée vers BigQuery pour le suivi FinOps, conformément au Principe V de la Constitution.
    """
    try:
        bq_client = bigquery.Client(project=settings.gcp_project_id)
        record = {
            "run_id": run_id,
            "job_type": job_type, # "RESELL" or "REGIE"
            "item_id": item_id,
            "client_id": client_id,
            "status": status, # "SUCCESS", "FAILED", "SKIPPED"
            "total_amount": total_amount,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        errors = bq_client.insert_rows_json(settings.bq_trace_table, [record])
        if errors:
            app_logger.error(f"Failed to export FinOps trace: {errors}")
        else:
            app_logger.debug(f"FinOps trace exported for {client_id}")
    except Exception as e:
        app_logger.error(f"FinOps exporter error: {e}")

