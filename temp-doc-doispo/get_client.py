import requests
import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("SELLSY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SELLSY_CLIENT_SECRET")

# get token
token = requests.post(
    "https://login.sellsy.com/oauth2/access-tokens",
    data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
).json()["access_token"]

headers = {
    "Authorization": f"Bearer {token}"
}

r = requests.get(
    "https://api.sellsy.com/v2/companies",
    headers=headers
)

companies = r.json()["data"]

print(companies[0])