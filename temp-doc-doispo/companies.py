from sellsy_client import SellsyClient


class CompaniesAPI:

    def __init__(self):
        self.client = SellsyClient()

    def list_companies(self):

        return self.client.request(
            "GET",
            "/companies"
        )

    def create_company(self, name, email=None):

        payload = {
            "name": name
        }

        if email:
            payload["email"] = email

        return self.client.request(
            "POST",
            "/companies",
            payload
        )