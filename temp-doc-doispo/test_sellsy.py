from companies import CompaniesAPI
from invoices import InvoicesAPI


companies = CompaniesAPI()
invoices = InvoicesAPI()


# créer un client test
company = companies.create_company(
    "Test API Client",
    "test@example.com"
)

company_id = company["id"]

print("Company created:", company_id)


# créer facture
invoice = invoices.create_invoice(
    company_id,
    "Consulting API",
    1200
)

print("Invoice created:", invoice)