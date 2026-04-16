import datetime
import time
from typing import List, Dict, Any
import requests

from core.config import settings
from core.logger import app_logger, send_slack_alert
from utils.resilience import http_retry_decorator

class SellsyAuthManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SellsyAuthManager, cls).__new__(cls)
            cls._instance._token = None
            cls._instance._expires_at = 0
        return cls._instance

    @http_retry_decorator(max_attempts=3, min_wait=1, max_wait=5)
    def fetch_token(self) -> str:
        """Récupère ou rafraîchit le token OAuth2 Sellsy en mémoire."""
        if self._token and time.time() < self._expires_at:
            return self._token

        app_logger.info("Renouvellement du token OAuth2 Sellsy...")
        url = "https://login.sellsy.com/oauth2/access-tokens"
        
        data = {
            "grant_type": "client_credentials",
            "client_id": settings.sellsy_client_id,
            "client_secret": settings.sellsy_client_secret
        }
        
        try:
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            payload = response.json()
            self._token = payload["access_token"]
            expires_in = payload.get("expires_in", 3600)
            
            self._expires_at = time.time() + expires_in - 300
            app_logger.info("Nouveau token Sellsy acquis.")
            
            return self._token
        except requests.RequestException as e:
            app_logger.error(f"Echec critique d'authentification OAuth2 Sellsy: {e}")
            raise Exception("Impossible d'acquérir le token Sellsy") from e

def get_previous_month_name(current_date: datetime.date) -> str:
    """
    Retourne le nom du mois précédent (en français) et l'année.
    """
    months = [
        'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 
        'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
    ]
    prev_month_idx = current_date.month - 2
    if prev_month_idx < 0:
        prev_month_idx = 11
    
    year = current_date.year if current_date.month > 1 else current_date.year - 1
    return f"{months[prev_month_idx]} {year}"

def format_sellsy_payload(client_id: int, pipeline_name: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Construit le payload de brouillon de facture attendu par Sellsy API v2.
    Respecte l'exigence FR-007 : Date = exécution, Objet = M-1.
    """
    today = datetime.date.today()
    prev_month_str = get_previous_month_name(today)
    
    rows = []
    for item in items:
        rows.append({
            "type": "single",
            "description": item.get("description", "Prestation"),
            "quantity": str(item.get("quantity", 1)),
            "unit_amount": str(item.get("amount", 0))
        })
    
    payload = {
        "related": [{"id": client_id, "type": "company"}],
        "date": today.isoformat(),
        "subject": f"Facturation {pipeline_name} - {prev_month_str}",
        "rows": rows
    }
    return payload

class SellsyClientError(Exception):
    """Exception custom pour le client Sellsy"""
    pass

class SellsyClient:
    """
    Client centralisé pour interagir avec l'API Sellsy 
    (Création de factures en mode 'Draft' - Régie & Resell).
    """
    def __init__(self):
        self.auth_manager = SellsyAuthManager()
        self.base_url = settings.sellsy_api_base

    def _get_headers(self) -> dict:
        token = self.auth_manager.fetch_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    @http_retry_decorator(max_attempts=3, min_wait=1, max_wait=10)
    def create_draft_invoice(self, client_id: int, pipeline_name: str, items: List[Dict[str, Any]]) -> dict:
        """
        Génère un brouillon de facture via Sellsy.
        Déclenche une alerte Slack en cas de client manquant ou inconnu.
        """
        if not client_id:
            msg = f"Client Sellsy manquant (mapping introuvable) pour la facturation {pipeline_name}"
            app_logger.error(msg)
            send_slack_alert(msg, details={"items": items})
            raise SellsyClientError(msg)

        payload = format_sellsy_payload(client_id, pipeline_name, items)
        url = f"{self.base_url}/invoices"
        
        try:
            app_logger.info(f"Création facture brouillon Sellsy pour client '{client_id}' (Pipeline {pipeline_name})...")
            response = requests.post(url, json=payload, headers=self._get_headers())
            
            # Gestion explicite des erreurs de mapping ou de payload 400/404
            if response.status_code in {400, 404}:
                error_msg = f"Rejet Sellsy (Client {client_id} introuvable ou erreur payload)"
                app_logger.error(f"{error_msg}: {response.text}")
                send_slack_alert(error_msg, details=response.json() if "{" in response.text else {"error": response.text})
            
            response.raise_for_status()
            
            app_logger.info(f"Facture brouillon créée avec succès pour {client_id}")
            return response.json()
            
        except requests.RequestException as e:
            app_logger.error(f"Erreur API Sellsy lors de la facturation {pipeline_name} (Client {client_id}): {str(e)}")
            raise
