#!/bin/bash
# Script de déploiement des Cloud Schedulers (FR-001)

PROJECT_ID=${PROJECT_ID:-"votre-projet-gcp"}
REGION=${REGION:-"europe-west1"}
SERVICE_URL=${SERVICE_URL:-"https://facturation-app-abcde-ew.a.run.app"}
SERVICE_ACCOUNT=${SERVICE_ACCOUNT:-"facturation-sa@${PROJECT_ID}.iam.gserviceaccount.com"}

echo "Déploiement des tâches Cloud Scheduler pour le projet $PROJECT_ID ($REGION)..."

# Pipeline Régie : Exécution le 1er du mois à 02:00
gcloud scheduler jobs create http facturation-regie-job \
  --location=$REGION \
  --schedule="0 2 1 * *" \
  --time-zone="Europe/Paris" \
  --uri="${SERVICE_URL}/regie" \
  --http-method=POST \
  --oidc-service-account-email=$SERVICE_ACCOUNT \
  --oidc-token-audience=$SERVICE_URL \
  --description="Déclenchement automatique de la facturation Régie (Napta -> Sellsy)" || \
  gcloud scheduler jobs update http facturation-regie-job \
  --location=$REGION \
  --schedule="0 2 1 * *" \
  --time-zone="Europe/Paris" \
  --uri="${SERVICE_URL}/regie" \
  --http-method=POST \
  --oidc-service-account-email=$SERVICE_ACCOUNT \
  --oidc-token-audience=$SERVICE_URL

# Pipeline Resell : Exécution le 1er du mois à 03:00 (après Régie)
gcloud scheduler jobs create http facturation-resell-job \
  --location=$REGION \
  --schedule="0 3 1 * *" \
  --time-zone="Europe/Paris" \
  --uri="${SERVICE_URL}/resell" \
  --http-method=POST \
  --oidc-service-account-email=$SERVICE_ACCOUNT \
  --oidc-token-audience=$SERVICE_URL \
  --description="Déclenchement automatique de la facturation Resell (GCP/DV360 -> Sellsy)" || \
  gcloud scheduler jobs update http facturation-resell-job \
  --location=$REGION \
  --schedule="0 3 1 * *" \
  --time-zone="Europe/Paris" \
  --uri="${SERVICE_URL}/resell" \
  --http-method=POST \
  --oidc-service-account-email=$SERVICE_ACCOUNT \
  --oidc-token-audience=$SERVICE_URL

echo "Terminé."
