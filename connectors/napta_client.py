import time
from typing import List, Dict, Any
import requests
from datetime import datetime, timedelta

from core.config import settings
from core.logger import app_logger
from utils.resilience import http_retry_decorator

class NaptaClientError(Exception):
    """Base exception for Napta API"""
    pass

class NaptaAuthManager:
    """
    Singleton pour gérer le cycle de vie du token OAuth2 (valide 2h).
    Renouvellement automatique à T-5min.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NaptaAuthManager, cls).__new__(cls)
            cls._instance._token = None
            cls._instance._expires_at = None
        return cls._instance
        
    @http_retry_decorator(max_attempts=3, min_wait=2, max_wait=10)
    def get_valid_token(self) -> str:
        """Récupère un token stocké valide ou en génère un nouveau si expiré/proche de l'expiration."""
        # T-5min margin (300 seconds)
        now = datetime.utcnow()
        if self._token and self._expires_at and (self._expires_at - now).total_seconds() > 300:
            return self._token
            
        app_logger.info("Génération d'un nouveau token Napta (OAuth2 Client Credentials)...")
        payload = {
            "grant_type": "client_credentials",
            "client_id": settings.napta_client_id,
            "client_secret": settings.napta_client_secret
        }
        
        try:
            res = requests.post(settings.napta_auth_url, data=payload)
            res.raise_for_status()
            data = res.json()
            
            self._token = data.get("access_token")
            expires_in = int(data.get("expires_in", 7200))  # Par défaut 2h
            self._expires_at = now + timedelta(seconds=expires_in)
            
            app_logger.info("Nouveau jeton Napta acquis avec succès.")
            return self._token
            
        except requests.RequestException as e:
            app_logger.error(f"Echec de l'authentification Napta: {e}")
            raise NaptaClientError(f"Auth failed: {e}")

class NaptaClient:
    """
    Client de consommation des endpoints Napta v0 (/time_entries, /assignments, etc.).
    Supporte la pagination et le rate limiting.
    """
    def __init__(self):
        self.base_url = settings.napta_api_base
        self.auth_manager = NaptaAuthManager()

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.auth_manager.get_valid_token()}",
            "Accept": "application/json"
        }
        
    @http_retry_decorator(max_attempts=5, min_wait=1, max_wait=20)
    def _paginated_get(self, endpoint: str, params: dict = None) -> List[Dict[str, Any]]:
        """
        Helper pour requêter avec backoff 429 et gérer la pagination cursor-based (limit=500 max).
        Ajoute un micro-sleep de 0.1s entre les pages pour éviter le mur des 100/10s.
        """
        results = []
        if params is None:
            params = {}
            
        params['limit'] = 500
        url = f"{self.base_url}{endpoint}"
        
        while True:
            # Active rate-limiting throttle (100 req/10s = max 10.0 req/sec)
            time.sleep(0.12)
            
            app_logger.debug(f"Napta GET {url} | Params: {params}")
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            
            data = response.json()
            items = data.get("items", data.get("data", []))
            
            # Formats typiques de pagination
            if isinstance(items, list):
                results.extend(items)
            else:
                 app_logger.error("Format de payload Napta inattendu.")
                 break
                 
            # Extract cursor from meta or paging blocks
            meta = data.get("meta", {})
            cursor = meta.get("next_cursor")
            
            if cursor:
                params["cursor"] = cursor
            else:
                break
                
        return results

    def fetch_approved_time_entries(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Récupère uniquement les saisies de temps "approuvées" sur une période.
        """
        app_logger.info(f"Extraction des Time Entries Napta du {start_date} au {end_date}")
        params = {
            "approval_status": "approved",
            "date_gte": start_date,
            "date_lte": end_date
        }
        return self._paginated_get("/time_entries", params=params)

    def fetch_assignments(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Récupère les assignations (qui contiennent le `daily_fee_info` et custom_fields Sellsy).
        """
        app_logger.info(f"Extraction des Assignments Napta du {start_date} au {end_date}")
        params = {
            "starts_lte": end_date,
            "ends_gte": start_date
        }
        return self._paginated_get("/assignments", params=params)
