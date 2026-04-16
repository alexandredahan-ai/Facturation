import csv
import os
import time
import requests
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
        r = requests.post(TOKEN_URL, data={
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        })
        r.raise_for_status()
        resp = r.json()
        self.access_token = resp["access_token"]
        self.token_expiry = time.time() + resp["expires_in"] - 60
        return self.access_token

    def request(self, method, endpoint, payload=None):
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        url = f"{API_BASE}{endpoint}"
        r = requests.request(method, url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()

OUTPUT_FILE = "clients.csv"
PAGE_SIZE = 100


def fetch_all(client, endpoint):
    """Récupère toutes les pages d'un endpoint paginé."""
    results = []
    offset = 0

    while True:
        response = client.request(
            "GET",
            f"{endpoint}?limit={PAGE_SIZE}&offset={offset}"
        )

        data = response.get("data", [])
        results.extend(data)

        pagination = response.get("pagination", {})
        total = pagination.get("total", len(data))

        offset += len(data)

        if offset >= total or not data:
            break

    return results


def extract_company(item):
    """Extrait les champs utiles d'une company."""
    address = item.get("address") or {}
    return {
        "type": "company",
        "id": item.get("id", ""),
        "name": item.get("name", ""),
        "email": item.get("email", ""),
        "phone": item.get("phone_number", "") or item.get("phone", ""),
        "website": item.get("website", ""),
        "siret": item.get("siret", ""),
        "vat_number": item.get("vat_number", ""),
        "address": address.get("address_line_1", ""),
        "city": address.get("city", ""),
        "zipcode": address.get("postal_code", ""),
        "country": address.get("country_code", ""),
    }


def extract_contact(item):
    """Extrait les champs utiles d'un contact individuel."""
    address = item.get("address") or {}
    first = item.get("first_name", "") or ""
    last = item.get("last_name", "") or ""
    return {
        "type": "contact",
        "id": item.get("id", ""),
        "name": f"{first} {last}".strip(),
        "email": item.get("email", ""),
        "phone": item.get("mobile_number", "") or item.get("phone_number", ""),
        "website": item.get("website", ""),
        "siret": "",
        "vat_number": "",
        "address": address.get("address_line_1", ""),
        "city": address.get("city", ""),
        "zipcode": address.get("postal_code", ""),
        "country": address.get("country_code", ""),
    }


def main():
    client = SellsyClient()

    print("Récupération des companies...")
    companies = fetch_all(client, "/companies")
    print(f"  → {len(companies)} companies trouvées")

    print("Récupération des contacts...")
    contacts = fetch_all(client, "/contacts")
    print(f"  → {len(contacts)} contacts trouvés")

    rows = []
    for item in companies:
        rows.append(extract_company(item))
    for item in contacts:
        rows.append(extract_contact(item))

    if not rows:
        print("Aucun client trouvé.")
        return

    fieldnames = ["type", "id", "name", "email", "phone", "website",
                  "siret", "vat_number", "address", "city", "zipcode", "country"]

    output_path = os.path.join(os.path.dirname(__file__), OUTPUT_FILE)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nExport terminé : {len(rows)} clients → {output_path}")


if __name__ == "__main__":
    main()
