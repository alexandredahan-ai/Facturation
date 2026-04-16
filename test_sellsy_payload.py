import requests
from connectors.sellsy_client import SellsyClient

client = SellsyClient()
headers = client._get_headers()
url = f"{client.base_url}/companies/search"
res = requests.post(url, json={"filter": {}}, headers=headers)
print("Search code:", res.status_code)
if res.status_code == 400: print(res.text)

print("\nCompanies get:")
res2 = requests.get(f"{client.base_url}/companies", headers=headers)
print("Get code:", res2.status_code)
if res2.status_code == 200:
    for c in res2.json().get("data", [])[:1]:
        print("Id:", c.get("id"))
