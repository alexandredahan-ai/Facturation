import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Config(BaseSettings):
    """
    Configuration de l'application Facturation Automatisation.
    Charge les variables depuis l'environnement ou un fichier .env
    """
    
    # Projet GCP
    gcp_project_id: str = Field(..., validation_alias="PROJECT_ID")
    
    # BigQuery
    bq_resell_table: str = Field("projet.dataset.resell_converteo", validation_alias="TABLE_RESELL")
    bq_trace_table: str = Field("projet.dataset.finops_traces", validation_alias="TABLE_TRACE")
    
    # GCS Trace Export
    gcs_trace_bucket: str = Field("", validation_alias="GCS_TRACE_BUCKET")
    
    # Napta Credentials
    napta_client_id: str = Field(..., validation_alias="NAPTA_CLIENT_ID")
    napta_client_secret: str = Field(..., validation_alias="NAPTA_CLIENT_SECRET")
    napta_auth_url: str = Field("https://auth.napta.io/oauth/token", validation_alias="NAPTA_AUTH_URL")
    napta_api_base: str = Field("https://api.napta.io/integration/v0", validation_alias="NAPTA_API_BASE")
    
    # Sellsy API
    sellsy_api_key: str = Field(..., validation_alias="SELLSY_API_KEY")
    sellsy_api_base: str = Field("https://api.sellsy.com/v2", validation_alias="SELLSY_API_BASE")
    
    # Slack Alerting
    slack_webhook_url: str = Field(..., validation_alias="SLACK_WEBHOOK_URL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

# Instance globale à importer
settings = Config()
