# Phase 1: Data Model & Entities

## 1. Entities from the User Source

### Entrée de Temps (Time Entry) - API Napta
- **`user_id`** (str): Identifiant de l'utilisateur.
- **`project_id`** (str): Identifiant du projet.
- **`assignment_id`** (str): Identifiant de la mission.
- **`duration`** (float): Durée en jours.
- **`is_half_day`** (bool): `starts_at_midday` ou `ends_at_midday` (vrai/faux).
- **`approval_status`** (str): Doit être `"approved"`.
- **`date`** (datetime/date): Jour ciblé.

### Ligne de Coût (Cost Record) - Resell (BigQuery/Sheet)
- **`cloud_channel_id`** (str): Clé de mappage.
- **`client_name`** (str): Nom d'affichage pour la validation humaine.
- **`cost_amount`** (float): Coût brut à la source.
- **`margin_rate`** (float): Taux de marge applicable (selon les règles de contrat).

### Brouillon de Facture (Draft Invoice) - API Sellsy
- **`sellsy_company_id`** (int): Identifiant exact du client cible dans Sellsy.
- **`invoice_date`** (date): Date de création du document.
- **`subject`** (str): Ex: "Facturation Régie - [MOIS M-1] - [PROJET]".
- **`lines`** (List[LineItem]): Détail par ressource ou par service GCP.
- **`status`** (str): Constant, forcement `"draft"`.

## 2. Interface Contracts

### /contracts/sellsy_draft.json
Le modèle de payload envoyé à l'API Sellsy pour créer la facture :
```json
{
  "client_id": 12345,
  "date": "2026-05-15",
  "subject": "Facturation GCP - Avril 2026",
  "items": [
    {
      "description": "Consommation Compute Engine",
      "quantity": 1,
      "amount": 1050.50
    }
  ]
}
```
*Note: Les structures exactes devront matcher la documentation de l'API Sellsy v2.*
See /specs/001-facturation-automatisation/contracts for specific JSON contracts.
