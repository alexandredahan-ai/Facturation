import requests
import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("SELLSY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SELLSY_CLIENT_SECRET")

url = "https://login.sellsy.com/oauth2/access-tokens"

data = {
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET
}

response = requests.post(url, data=data)

print("STATUS:", response.status_code)
print("RESPONSE:", response.text)