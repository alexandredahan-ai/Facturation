from sellsy_client import SellsyClient


class InvoicesAPI:

    def __init__(self):
        self.client = SellsyClient()

    def create_invoice(self, company_id, label, price):

        payload = {
            "company_id": company_id,
            "rows": [
                {
                    "type": "item",
                    "name": label,
                    "quantity": 1,
                    "unit_amount": price
                }
            ]
        }

        return self.client.request(
            "POST",
            "/invoices",
            payload
        )

    def validate_invoice(self, invoice_id):

        return self.client.request(
            "POST",
            f"/invoices/{invoice_id}/validate"
        )