import requests
from core.config import settings

url = "https://login.sellsy.com/oauth2/access-tokens"
data = {
    "grant_type": "client_credentials",
    "client_id": settings.sellsy_client_id,
    "client_secret": settings.sellsy_client_secret
}
headers = {"Content-Type": "application/x-www-form-urlencoded"}
res = requests.post(url, data=data, headers=headers)
print(res.status_code)
print(res.text)
