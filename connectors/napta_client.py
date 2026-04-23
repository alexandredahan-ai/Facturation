import time
from typing import List, Dict, Any, Optional
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
    Singleton pour gérer le cycle de vie du token OAuth2 Napta (valide 24h).
    Réutilise le token en cache tant qu'il est valide, renouvelle à T-5min.
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
        """Récupère un token valide ou en demande un nouveau si expiré (T-5min de marge)."""
        now = datetime.utcnow()
        if self._token and self._expires_at and (self._expires_at - now).total_seconds() > 300:
            return self._token
            
        app_logger.info("Renouvellement du token Napta (OAuth2 Client Credentials)...")
        try:
            res = requests.post(
                settings.napta_auth_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.napta_client_id,
                    "client_secret": settings.napta_client_secret,
                    "audience": settings.napta_audience,
                },
                headers={"content-type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            res.raise_for_status()
            data = res.json()
            
            self._token = data["access_token"]
            expires_in = int(data.get("expires_in", 86400))
            self._expires_at = now + timedelta(seconds=expires_in)
            
            app_logger.info(f"Token Napta acquis (expire dans {expires_in}s).")
            return self._token
            
        except requests.RequestException as e:
            app_logger.error(f"Echec authentification Napta: {e}")
            raise NaptaClientError(f"Auth failed: {e}")


class NaptaClient:
    """
    Client Napta Integration API v0.
    Pagination cursor-based, rate limiting 100 req/10s.
    """
    def __init__(self):
        self.base_url = settings.napta_api_base
        self.auth_manager = NaptaAuthManager()

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.auth_manager.get_valid_token()}",
            "Accept": "application/json",
        }
        
    def _paginated_get(self, endpoint: str, params: Optional[dict] = None) -> List[Dict[str, Any]]:
        """
        Requête paginée Napta (cursor-based).
        Pagination param: pagination[cursor], réponse: pagination.has_more_available + next_cursor.
        Throttle 0.12s entre pages pour respecter 100 req/10s.
        """
        results = []
        if params is None:
            params = {}
        params.setdefault("pagination[limit]", 500)
            
        url = f"{self.base_url}{endpoint}"
        
        while True:
            time.sleep(0.12)
            
            app_logger.debug(f"Napta GET {endpoint} | cursor={params.get('pagination[cursor]', 'start')}")
            response = self._do_get(url, params)
            
            body = response.json()
            items = body.get("data", [])
            if isinstance(items, list):
                results.extend(items)
                 
            pagination = body.get("pagination", {})
            if pagination.get("has_more_available") and pagination.get("next_cursor"):
                params["pagination[cursor]"] = pagination["next_cursor"]
            else:
                break
                
        app_logger.info(f"Napta {endpoint} : {len(results)} éléments récupérés.")
        return results

    @http_retry_decorator(max_attempts=5, min_wait=1, max_wait=20)
    def _do_get(self, url: str, params: dict) -> requests.Response:
        """GET unitaire avec retry/backoff sur 429 et 5xx."""
        response = requests.get(url, headers=self._get_headers(), params=params, timeout=60)
        if response.status_code >= 400:
            app_logger.error(f"Napta API error {response.status_code}: {response.text[:500]}")
        response.raise_for_status()
        return response

    def fetch_time_entries(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Récupère les time entries d'une période via les filtres serveur date[ge]/date[le].
        Retourne toutes les entrées (filtrées, validées ou non) pour la période.
        Structure : { date, workload, is_validated, status, user: {napta_id, email}, project: {napta_id} }
        """
        app_logger.info(f"Extraction Time Entries Napta {start_date} → {end_date}")
        params = {
            "date[ge]": start_date,
            "date[le]": end_date,
        }
        return self._paginated_get("/time_entries", params=params)

    def fetch_validated_time_entries(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Récupère uniquement les time entries validées (is_validated=True) d'une période.
        Filtre serveur sur les dates, filtre client sur is_validated (FR-002).
        """
        all_entries = self.fetch_time_entries(start_date, end_date)
        validated = [te for te in all_entries if te.get("is_validated")]
        app_logger.info(f"Time entries validées : {len(validated)}/{len(all_entries)}")
        return validated

    def _batched_fetch(self, endpoint: str, filter_key: str, ids: List[int],
                       extra_params: Optional[dict] = None, batch_size: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch par lots pour éviter des URLs trop longues avec le filtre [in].
        Découpe ids en chunks de batch_size et agrège les résultats.
        Pause 1s entre chaque batch pour respecter le rate limit (100 req/10s).
        En cas d'erreur sur un batch, log et continue avec les autres.
        """
        results = []
        failed_ids = []
        total_batches = (len(ids) + batch_size - 1) // batch_size
        for idx, i in enumerate(range(0, len(ids), batch_size)):
            chunk = ids[i:i + batch_size]
            app_logger.debug(f"Batch {idx+1}/{total_batches} : {len(chunk)} IDs")
            params = {filter_key: ",".join(str(pid) for pid in chunk)}
            if extra_params:
                params.update(extra_params)
            try:
                results.extend(self._paginated_get(endpoint, params=params))
            except Exception as e:
                app_logger.warning(f"Batch {idx+1}/{total_batches} échoué ({endpoint}): {e} — IDs ignorés: {chunk}")
                failed_ids.extend(chunk)
            if idx < total_batches - 1:
                time.sleep(1)  # Pause inter-batch pour rate limiting
        if failed_ids:
            app_logger.warning(f"{len(failed_ids)} IDs ignorés sur {endpoint} à cause d'erreurs API Napta")
        return results

    def fetch_assignments_for_projects(self, project_napta_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Récupère les assignments pour une liste de projets (filtre serveur project.napta_id[in]).
        Batché par lots de 50 pour éviter les URLs trop longues.
        """
        if not project_napta_ids:
            return []
        
        app_logger.info(f"Extraction Assignments Napta pour {len(project_napta_ids)} projets")
        results = self._batched_fetch(
            "/assignments", "project.napta_id[in]", project_napta_ids,
            extra_params={"simulated[eq]": "false"},
        )
        app_logger.info(f"Assignments récupérés : {len(results)}")
        return results

    def fetch_projects(self, project_napta_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Récupère les projets par ID (pour obtenir le client et les custom_fields).
        Batché par lots de 50 pour éviter les URLs trop longues.
        """
        if not project_napta_ids:
            return []
        
        app_logger.info(f"Extraction Projects Napta pour {len(project_napta_ids)} projets")
        results = self._batched_fetch("/projects", "id.napta_id[in]", project_napta_ids)
        app_logger.info(f"Projects récupérés : {len(results)}")
        return results

    def fetch_leaves(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Récupère les congés/absences pour la gestion des demi-journées (FR-004).
        Structure réelle : { category, start_date, end_date, starts_at_midday, ends_at_midday, user }
        """
        app_logger.info(f"Extraction des Leaves Napta du {start_date} au {end_date}")
        all_leaves = self._paginated_get("/leaves")
        
        filtered = [
            lv for lv in all_leaves
            if lv.get("start_date", "9999") <= end_date
            and lv.get("end_date", "0000") >= start_date
        ]
        app_logger.info(f"Congés dans la période : {len(filtered)}/{len(all_leaves)}")
        return filtered
