import requests
from connectors.sellsy_client import SellsyClient

client = SellsyClient()
headers = client._get_headers()

url = f"{client.base_url}/invoices/52700222?embed[]=rows"
res = requests.get(url, headers=headers)
print(res.text[:1500])
