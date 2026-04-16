import requests
from connectors.sellsy_client import SellsyAuthManager
from core.config import settings

am = SellsyAuthManager()
headers = {
    "Authorization": f"Bearer {am.fetch_token()}",
}
print(headers)
resp = requests.post(f"{settings.sellsy_api_base}/companies/search", json={"filter": {"name": "Test"}}, headers=headers)
print(resp.status_code, resp.text)
