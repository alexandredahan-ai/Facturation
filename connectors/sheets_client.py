import os
import json
from typing import List, Dict, Any
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from core.logger import app_logger

class GoogleSheetsClientError(Exception):
    """Exception custom pour le client Google Sheets"""
    pass

class GoogleSheetsClient:
    """
    Client pour lire les données DV360 de Clara S. via Google Sheets.
    """
    def __init__(self, spreadsheet_id: str, range_name: str):
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        self.spreadsheet_id = spreadsheet_id
        self.range_name = range_name
        
        try:
            # Assuming GCP standard behavior: GOOGLE_APPLICATION_CREDENTIALS must be set
            self.credentials = Credentials.from_service_account_file(
                os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'credentials.json'),
                scopes=self.scopes
            )
            self.service = build('sheets', 'v4', credentials=self.credentials)
        except Exception as e:
            app_logger.error(f"Erreur d'initialisation du client Sheets: {e}")
            raise GoogleSheetsClientError(f"Erreur init Sheets: {e}")

    def fetch_dv360_data(self) -> List[Dict[str, Any]]:
        """
        Extrait les données de consommation DV360 depuis le tableur Sheets (22 colonnes).
        """
        app_logger.info(f"Extraction des données DV360 depuis la Sheet ID: {self.spreadsheet_id}")
        
        try:
            sheet = self.service.spreadsheets()
            result = sheet.values().get(spreadsheetId=self.spreadsheet_id, range=self.range_name).execute()
            values = result.get('values', [])
            
            if not values:
                app_logger.warning("Aucune donnée DV360 trouvée dans le Sheet.")
                return []
                
            headers = values[0]
            records = []
            
            for row in values[1:]:
                # Assure that row length matches headers if trailing columns are empty
                row_data = row + [''] * (len(headers) - len(row))
                record = dict(zip(headers, row_data))
                records.append(record)
                
            app_logger.info(f"{len(records)} lignes de données extraites de Google Sheets.")
            return records
            
        except Exception as e:
            msg = f"Erreur lors de l'extraction Google Sheets: {str(e)}"
            app_logger.error(msg)
            raise GoogleSheetsClientError(msg)

