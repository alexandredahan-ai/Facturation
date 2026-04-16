import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = "https://login.sellsy.com/oauth2/access-tokens"
API_BASE = "https://api.sellsy.com/v2"


class SellsyClient:

    def __init__(self):

        self.client_id = os.getenv("SELLSY_CLIENT_ID")
        self.client_secret = os.getenv("SELLSY_CLIENT_SECRET")

        self.access_token = None
        self.token_expiry = 0

    def _get_token(self):

        if self.access_token and time.time() < self.token_expiry:
            return self.access_token

        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        r = requests.post(TOKEN_URL, data=data)
        r.raise_for_status()

        response = r.json()

        self.access_token = response["access_token"]
        self.token_expiry = time.time() + response["expires_in"] - 60

        return self.access_token

    def request(self, method, endpoint, payload=None):

        token = self._get_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        url = f"{API_BASE}{endpoint}"

        r = requests.request(
            method,
            url,
            json=payload,
            headers=headers
        )

        r.raise_for_status()

        return r.json()