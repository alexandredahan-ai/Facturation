# Pipeline Régie — Guide d'utilisation

Pipeline de facturation automatique des prestations Régie : extraction des temps saisis dans **Napta**, croisement avec les TJM, et création de **brouillons de factures** dans **Sellsy**.

---

## Table des matières

1. [Prérequis](#1-prérequis)
2. [Architecture & fichiers](#2-architecture--fichiers)
3. [Étape 1 — Initialisation du mapping](#3-étape-1--initialisation-du-mapping)
4. [Étape 2 — Complétion manuelle du CSV](#4-étape-2--complétion-manuelle-du-csv)
5. [Étape 3 — Exécution de la pipeline](#5-étape-3--exécution-de-la-pipeline)
6. [Logique interne de la pipeline](#6-logique-interne-de-la-pipeline)
7. [Limites connues de l'API Napta](#7-limites-connues-de-lapi-napta)
8. [Dépannage](#8-dépannage)

---

## 1. Prérequis

- **Python 3.9+** avec `venv` activé
- Fichier `.env` configuré avec les credentials :
  - Napta : `NAPTA_AUTH_URL`, `NAPTA_CLIENT_ID`, `NAPTA_CLIENT_SECRET`, `NAPTA_AUDIENCE`, `NAPTA_API_BASE`
  - Sellsy : `SELLSY_CLIENT_ID`, `SELLSY_CLIENT_SECRET`, `SELLSY_TOKEN_URL`, `SELLSY_API_BASE`
- Dépendances installées : `pip install -r requirements.txt`

```bash
source venv/bin/activate
```

---

## 2. Architecture & fichiers

```
.
├── main_regie.py                    # Orchestrateur pipeline Régie
├── mapping_napta_sellsy.csv         # Mapping complet (production)
├── mapping_napta_sellsy_test.csv    # Mapping de test (3 clients)
├── connectors/
│   ├── napta_client.py              # Client API Napta v0
│   └── sellsy_client.py             # Client API Sellsy v2
├── tools/
│   └── init_client_mapping.py       # Script d'initialisation du mapping
├── core/
│   ├── config.py                    # Configuration (.env)
│   └── logger.py                    # Logging
└── utils/
    └── resilience.py                # Retry/backoff HTTP
```

### Flux de données

```
Napta (time entries + assignments)
        │
        ▼
   main_regie.py ──── mapping CSV ──── Sellsy (brouillons factures)
```

---

## 3. Étape 1 — Initialisation du mapping

Le script `tools/init_client_mapping.py` génère le fichier CSV de mapping Napta → Sellsy par **fuzzy matching** automatique.

### Exécution

```bash
python tools/init_client_mapping.py \
  --start 2026-01-01 \
  --end 2026-03-31 \
  --threshold 0.45 \
  --output mapping_napta_sellsy.csv
```

| Paramètre     | Défaut                      | Description                                         |
|----------------|-----------------------------|-----------------------------------------------------|
| `--start`      | `2026-01-01`                | Début de la période Napta pour détecter les clients  |
| `--end`        | `2026-03-31`                | Fin de la période                                    |
| `--threshold`  | `0.45`                      | Seuil de similarité (0–1) pour le fuzzy matching     |
| `--output`     | `mapping_napta_sellsy.csv`  | Fichier CSV de sortie                                |

### Ce que fait le script

1. **Récupère les companies Sellsy** (tous types : clients, prospects, etc.)
2. **Extrait les clients Napta** à partir des time entries validées sur la période → identifie les noms de clients uniques (`project.client`) et leurs `project_ids`
3. **Fuzzy matching** (difflib `SequenceMatcher`) entre chaque nom Napta et les companies Sellsy
4. **Génère un CSV** avec 3 sections

### Structure du CSV généré

Le CSV utilise le séparateur `;` et contient 3 sections :

**Section 1 — `MAPPING PROPOSE`** : matchs automatiques triés par score décroissant

| Colonne               | Exemple                    | Description                                  |
|------------------------|----------------------------|----------------------------------------------|
| `napta_client_name`    | Abeille Assurances         | Nom du client dans Napta                     |
| `napta_nb_projets`     | 20                         | Nombre de projets Napta pour ce client       |
| `sellsy_company_id`    | 57866865                   | ID Sellsy proposé par le matching            |
| `sellsy_company_name`  | Abeille Assurances         | Nom de la company Sellsy                     |
| `sellsy_type`          | client                     | Type Sellsy (client, prospect…)              |
| `match_score`          | 1.0                        | Score de similarité (0–1)                    |
| `VALIDE (oui/non)`     | oui                        | **À remplir** : `oui` pour valider la ligne  |
| `napta_project_ids`    | 8556\|10225\|10637         | Project IDs Napta (séparés par `\|`)         |

**Section 2 — `CLIENTS NAPTA SANS MATCH`** : clients sans correspondance Sellsy (à compléter manuellement)

**Section 3 — `REFERENTIEL SELLSY COMPLET`** : toutes les companies Sellsy (pour copier-coller les IDs)

> **Note** : les matchs avec un score ≥ 0.8 sont automatiquement pré-remplis avec `VALIDE = oui`. Tous les autres doivent être validés manuellement.

---

## 4. Étape 2 — Complétion manuelle du CSV

Ouvrir `mapping_napta_sellsy.csv` dans un tableur (Excel, Google Sheets) ou un éditeur texte.

### Actions à effectuer

1. **Vérifier les matchs automatiques** (Section 1) :
   - Si le match est correct → mettre `oui` dans la colonne `VALIDE`
   - Si le match est incorrect → corriger `sellsy_company_id` et `sellsy_company_name` en copiant depuis la Section 3, puis mettre `oui`
   - Si le client ne doit pas être facturé → laisser vide ou mettre `non`

2. **Compléter les clients sans match** (Section 2) :
   - Chercher le bon ID Sellsy dans la Section 3 (référentiel complet)
   - Remplir `sellsy_company_id`, `sellsy_company_name`, `sellsy_type`
   - Mettre `oui` dans `VALIDE`

3. **Contrôler le type Sellsy** : la company doit être de type `client` dans Sellsy pour pouvoir recevoir une facture

### Format simplifié (alternative)

Pour un test rapide ou un mapping partiel, on peut utiliser un CSV simple (sans sections `===`) :

```csv
napta_client_name;napta_nb_projets;sellsy_company_id;sellsy_company_name;sellsy_type;match_score;VALIDE (oui/non);napta_project_ids
MAIF;49;57866730;[TEST]Maif;client;0.85;oui;4144|4232|4357|...
```

> **Important** : seules les lignes avec `VALIDE = oui` et un `sellsy_company_id` valide seront traitées par la pipeline.

### Colonne `napta_project_ids`

Cette colonne est **pré-remplie automatiquement** par le script d'init. Elle contient les IDs de tous les projets Napta rattachés à ce client, séparés par `|`.

Elle est utilisée par la pipeline optimisée pour filtrer les time entries côté Python (voir section 6). **Ne pas modifier cette colonne** sauf si vous savez ce que vous faites.

Si cette colonne est absente ou vide pour tous les clients, la pipeline bascule automatiquement en **mode legacy** (plus lent).

---

## 5. Étape 3 — Exécution de la pipeline

### Commande

```bash
python main_regie.py \
  --start 2026-03-01 \
  --end 2026-03-31 \
  --mapping mapping_napta_sellsy.csv
```

| Paramètre   | Requis | Description                                               |
|--------------|--------|-----------------------------------------------------------|
| `--start`    | Oui    | Premier jour de la période à facturer (YYYY-MM-DD)        |
| `--end`      | Oui    | Dernier jour de la période (YYYY-MM-DD)                   |
| `--mapping`  | Non    | Chemin vers le CSV de mapping (défaut : `mapping_napta_sellsy.csv`) |

### Résultat

La pipeline crée un **brouillon de facture** dans Sellsy pour chaque client validé dans le CSV. Les factures sont visibles dans Sellsy > Facturation > Brouillons.

### Exemple de sortie

```
Mapping chargé : 3 clients validés depuis mapping_napta_sellsy_test.csv
Mapping: 3 clients, 377 project_ids ciblés
Time entries: 14472 total → 4051 validées & ciblées (sur 377 projets)
Assignments récupérés : 1510
Client 'MAIF' → Sellsy #57866730: 2 lignes, total 1530.00€
  ✓ Facture brouillon #52700295 créée pour 'MAIF'
Client 'CONVERTEO' → Sellsy #57866771: 21 lignes, total 16450.00€
  ✓ Facture brouillon #52700296 créée pour 'CONVERTEO'
Client 'Abeille Assurances' → Sellsy #57866865: 7 lignes, total 6475.00€
  ✓ Facture brouillon #52700297 créée pour 'Abeille Assurances'
Factures créées: 3 / Erreurs: 0 / Ignorés (non mappés): 0
```

### Contenu d'une facture brouillon

Chaque ligne de facture correspond à un **consultant × projet × TJM** agrégé sur la période :

```
Description : "Projet 12345 - alice@converteo.com (15.5j x 800.0€)"
Quantité    : 15.5      (total jours travaillés sur la période)
Prix unit.  : 800.0     (TJM issu de l'assignment Napta)
```

L'objet de la facture est : `Facturation Régie - {mois précédent}` (ex: "Facturation Régie - mars 2026").

---

## 6. Logique interne de la pipeline

### Flux optimisé (mode normal)

```
1. Charger le CSV mapping
   → Extraire l'ensemble des project_ids de tous les clients validés

2. GET /time_entries?date[ge]=...&date[le]=...
   → Récupère TOUTES les time entries de la période (filtre projet ignoré par l'API)

3. Filtrer côté Python
   → Ne garder que les TEs : is_validated=true AND project_id ∈ project_ids du mapping

4. GET /assignments?project.napta_id[in]=IDs
   → Récupère les assignments UNIQUEMENT pour les projets ayant des TEs filtrées
   → Ce filtre FONCTIONNE sur /assignments (contrairement à /time_entries)

5. Croisement TJM
   → Jointure (user_id, project_id) entre time entries et assignments
   → TJM = assignment.periods[-1].daily_fee_info.amount
   → Agrégation par (consultant, projet, TJM) : somme des jours

6. POST /invoices (Sellsy)
   → 1 brouillon par client avec N lignes agrégées
```

### Performance

| Étape          | Durée typique | Volume (mars 2026)       |
|----------------|---------------|--------------------------|
| Time entries   | ~25s          | 14 472 éléments          |
| Filtrage Python| < 1s          | → 4 051 ciblées          |
| Assignments    | ~30s          | 1 510 pour 58 projets    |
| Croisement     | < 1s          | 30 lignes facture        |
| POST Sellsy    | ~3s           | 3 factures               |
| **Total**      | **~57s**      |                          |

### Mode legacy (fallback)

Si le CSV ne contient pas de colonne `napta_project_ids`, la pipeline bascule automatiquement :
- Fetch toutes les time entries validées
- Fetch assignments pour **tous** les projets trouvés
- Fetch les détails de **tous** les projets (GET /projects)
- Plus lent (~2min30+) mais fonctionnel

---

## 7. Limites connues de l'API Napta

| Endpoint         | Filtre                      | Fonctionne ? |
|------------------|-----------------------------|--------------|
| `/time_entries`  | `date[ge]` / `date[le]`    | ✅ Oui        |
| `/time_entries`  | `project.napta_id[in]`     | ❌ Ignoré     |
| `/time_entries`  | `client[eq]`               | ❌ Ignoré     |
| `/assignments`   | `project.napta_id[in]`     | ✅ Oui        |
| `/assignments`   | `simulated[eq]`            | ✅ Oui        |
| `/projects`      | `client[eq]` / `[contains]`| ❌ Ignoré     |
| `/projects`      | `id.napta_id[in]`          | ✅ Oui        |

**Conséquence** : on est obligé de récupérer toutes les time entries de la période et de filtrer côté Python avec l'ensemble des `project_ids` du mapping.

---

## 8. Dépannage

### Erreur "Nombre de lignes de documents maximum atteint"

Sellsy impose une limite sur le nombre de lignes par facture. La pipeline agrège les lignes par (consultant, projet, TJM) pour éviter ce problème. Si l'erreur se reproduit, vérifier que la version de `correlate_tjm` dans `main_regie.py` utilise bien l'agrégation.

### NoneType sur `daily_fee_info` ou `periods`

Certains assignments Napta ont des champs `null`. Le code utilise le pattern `(x.get("key") or {})` au lieu de `x.get("key", {})` car `.get()` retourne `None` quand la clé existe avec une valeur `null`.

### Client non facturé (ignoré)

- Vérifier que `VALIDE = oui` dans le CSV
- Vérifier que le `sellsy_company_id` est correct
- Vérifier que la company Sellsy est de type `client` (pas `prospect`)

### Aucune time entry pour un client

Le client a peut-être des projets mais aucune saisie de temps validée sur la période. Vérifier dans Napta que les consultants ont bien saisi et validé leurs temps.

### Token expiré

Les tokens Napta (24h) et Sellsy sont renouvelés automatiquement avec une marge de 5 minutes. En cas d'échec, vérifier les credentials dans `.env`.
