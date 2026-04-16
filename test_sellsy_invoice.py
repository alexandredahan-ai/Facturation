import requests
from connectors.sellsy_client import SellsyAuthManager
from core.config import settings

am = SellsyAuthManager()
headers = {
    "Authorization": f"Bearer {am.fetch_token()}",
}
print("Trying to create invoice...")
data = {
  "client_id": 555,
  "related": {"id": 555, "type": "company"},
  "rows": [{"type": "item", "name": "test", "unit_price": 100, "quantity": 1}]
}
resp = requests.post(f"{settings.sellsy_api_base}/invoices", json=data, headers=headers)
print(resp.status_code, resp.text)

data2 = {
  "company_id": 555,
  "rows": [{"type": "item", "name": "test", "unit_price": 100, "quantity": 1}]
}
resp = requests.post(f"{settings.sellsy_api_base}/invoices", json=data2, headers=headers)
print(resp.status_code, resp.text)

