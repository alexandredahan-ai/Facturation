import requests
from connectors.sellsy_client import SellsyClient

client = SellsyClient()
headers = client._get_headers()

url = f"{client.base_url}/invoices"
res = requests.get(url, headers=headers)
print(res.status_code)
print(res.text[:1000])

