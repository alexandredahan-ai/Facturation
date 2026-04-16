import requests
import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("SELLSY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SELLSY_CLIENT_SECRET")

# get token
token_response = requests.post(
    "https://login.sellsy.com/oauth2/access-tokens",
    data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
)

token = token_response.json()["access_token"]

# call API
headers = {
    "Authorization": f"Bearer {token}"
}

response = requests.get(
    "https://api.sellsy.com/v2/companies",
    headers=headers
)

print(response.json())