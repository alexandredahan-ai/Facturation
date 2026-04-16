# Quickstart Guide: Automatisation Facturation

## Prerequisites
- Python 3.11+
- Service Account GCP credentials configured (`GOOGLE_APPLICATION_CREDENTIALS`)
- API Tokens (Napta Client/Secret, Sellsy API Token) exposed in `.env`
- `pytest` for running unit tests

## Local Development Setup

1. **Environment Initialization:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Set up `.env` file:**
   ```bash
   NAPTA_CLIENT_ID="xxx"
   NAPTA_CLIENT_SECRET="xxx"
   SELLSY_API_KEY="xxx"
   SLACK_WEBHOOK_URL="https://hooks.slack.com/..."
   PROJECT_ID="your-gcp-project"
   TABLE_RESELL="project.dataset.resell_converteo"
   ```

3. **Running the Pipelines Locally:**

   *For Resell (GCP/DV360):*
   ```bash
   python main_resell.py
   ```

   *For Régie (Napta):*
   ```bash
   # Mocks enabled manually in logic for local development if credentials aren't ready
   python main_regie.py
   ```

4. **Running Tests:**
   ```bash
   pytest tests/ -v
   ```
