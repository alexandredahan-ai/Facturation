# Feature Specification: Automatisation Facturation (Resell & Régie)

**Feature Branch**: `001-facturation-automatisation`  
**Created**: 15 avril 2026  
**Status**: Draft  
**Input**: User description: Cadrage projet pour l'automatisation de la facturation Resell et Régie vers Sellsy.

## Clarifications

### Session 2026-04-15
- Q: How should the system map/reconcile the client identities from the source systems (GCP, DV360, Napta) to the destination system (Sellsy)? → A: Mapping is done via provided source IDs (e.g., Cloud Channel ID) matched against lookup tables or fields, rather than strict name matching.
- Q: If the billing pipeline is executed twice for the same billing month, what should happen to the previously generated draft invoices in Sellsy? → A: Create a new draft invoice alongside the old one (Finance team cleans up duplicates manually).
- Q: Where and how should the "clear alerts" (e.g., for unrecognized clients or API failures) be delivered to the Finance team so they can act on them? → A: An automated message in a dedicated Slack/Google Chat channel for the Finance team.
- Q: For a billing run executed in a subsequent month, what should be the officially recorded 'Invoice Date' on the Sellsy draft invoices? → A: Both exist: the official Sellsy 'Invoice Date' is the actual execution date of the pipeline, while the content/label of the invoice clearly indicates the prior billing month.
- Q: How will the "monthly" process (for both Resell and Régie pipelines) ultimately be triggered in production? → A: An automated GCP Cloud Scheduler job.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatisation de la facturation Resell (Priority: P1)

En tant qu'équipe Finance/Ops, je veux que la facturation liée à la revente (Resell GCP / DV360) soit calculée, agrégée et poussée automatiquement sous forme de brouillons de factures, afin de limiter les erreurs humaines et le temps de traitement mensuel.

**Why this priority**: Ce flux ne possède aucun bloquant technique actuel et permet d'apporter de la valeur immédiatement en automatisant une tâche chronophage et génératrice de revenus.

**Independent Test**: L'équipe Finance peut lancer le traitement sur un mois donné et vérifier dans l'outil de facturation (Sellsy) que les brouillons générés correspondent exactement aux calculs de marges attendus depuis les sources de données (BigQuery, Sheets, etc.).

**Acceptance Scenarios**:

1. **Given** les données de facturation cloud (coûts) du mois précédent disponibles en base, **When** le processus de facturation mensuelle Resell est déclenché via Cloud Scheduler, **Then** les marges sont calculées et des brouillons de factures sont créés dans l'outil comptable pour chaque client.
2. **Given** une ligne de coût sans client reconnu, **When** le processus tente de générer la facture, **Then** une alerte claire est envoyée sur Slack/Google Chat et la ligne est ignorée ou signalée pour traitement manuel.

---

### User Story 2 - Automatisation de la facturation Régie / Staffing (Priority: P2)

En tant qu'équipe Finance, je veux que les jours facturables (temps passé validé) de l'outil de staffing (Napta) soient extraits, valorisés au bon Taux Journalier Moyen (TJM) et poussés sous forme de brouillons de factures, afin d'accélérer le cycle de facturation client.

**Why this priority**: Apporte une valeur métier majeure mais nécessite l'attente d'accès (credentials) à l'outil de staffing pour sa finalisation en production. Le développement initial peut s'appuyer sur des données simulées.

**Independent Test**: L'équipe Finance peut injecter un set de jours travaillés simulés (validés et non validés) et vérifier que seuls les jours validés, avec leurs demi-journées gérées correctement, génèrent des lignes de brouillons de factures au bon tarif.

**Acceptance Scenarios**:

1. **Given** un ensemble de temps saisis et approuvés pour un projet, **When** le processus de facturation Régie est exécuté via Cloud Scheduler, **Then** le système calcule le montant total (Temps x TJM) et génère le brouillon de facture correspondant.
2. **Given** des temps saisis mais *non approuvés*, **When** le processus est exécuté, **Then** ces temps ne sont pas inclus dans la facturation du mois.
3. **Given** la saisie d'une demi-journée de congé ou d'absence, **When** le processus est exécuté, **Then** la demi-journée est correctement déduite du temps facturable.

---

### Edge Cases

- **Quotas et limitations des systèmes tiers** : Que se passe-t-il si l'outil de staffing (Napta) rejette les requêtes pour cause de dépassement de limite (ex: 100 requêtes/10s) ? Le système doit intégrer un mécanisme de pause (exponential backoff) et réessayer.
- **Expiration des accès en cours de traitement** : Que se passe-t-il si le jeton d'accès temporaire (2h) expire avant la fin de l'extraction des dizaines de milliers de lignes ?
- **Clients introuvables dans l'outil cible** : Le système envoie une notification vers un canal Slack/Google Chat dédié à l'équipe financière.
- **Exécution multiple** : Si le processus est relancé (correction des temps), le système ne supprime pas les anciens brouillons ; il en recrée de nouveaux (l'équipe finance gère la déduplication manuellement dans Sellsy).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT s'exécuter mensuellement via un déclencheur automatisé (Cloud Scheduler) pour initier l'extraction des coûts cloud et des saisies Napta.
- **FR-002**: Le système DOIT extraire et filtrer les saisies de temps de l'outil de staffing pour ne conserver que les saisies au statut "approuvé".
- **FR-003**: Le système DOIT retrouver le taux journalier facturé exact applicable à chaque prestation de staffing.
- **FR-004**: Le système DOIT traiter la précision à la demi-journée près pour le calcul des jours facturables.
- **FR-005**: Le système DOIT regrouper et consolider les lignes facturables par ID/client et par projet respectif, en utilisant un mapping ID depuis la base (ex: ID Cloud Channel).
- **FR-006**: Le système DOIT créer les factures à l'état de "brouillon" dans l'outil comptable destinataire, sans jamais les émettre officiellement.
- **FR-007**: Le système DOIT enregistrer deux repères temporels : la Date de Facture sur l'outil Sellsy correspond à la date d'exécution script, tandis que la désignation/contenu de la facture cible explicitement le mois de facturation (M-1).
- **FR-008**: Le système DOIT gérer de manière unifiée toutes les interactions avec l'outil comptable (création de brouillons), indépendamment du type de facturation (Régie ou Resell).
- **FR-009**: Le système DOIT tracer chaque étape de transformation de données, conserver un historique vérifiable et émettre des alertes ciblées sur un chat d'équipe (Slack/Google Chat) en cas de client non reconnu ou d'erreur critique de l'API.

### Key Entities 

- **Entrée de Temps (Time Entry)** : Représente une période travaillée par une personne sur un projet. Attributs clés : durée (jours/demi-jours), statut d'approbation, lien vers l'assignation.
- **Mission/Assignation (Assignment)** : Représente l'affectation d'une personne à un projet. Attributs clés : Taux Journalier Moyen (TJM) facturé au client.
- **Ligne de Coût (Cost Record)** : Représente une consommation Cloud ou licence à refacturer. Attributs clés : montant brut, id client, type de revente.
- **Brouillon de Facture (Draft Invoice)** : Le document financier regroupant les lignes de refacturation (temps ou coûts purs) associé à un profil client identifié via un mappage ID précis.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : Exactitude financière : 100% des brouillons générés doivent correspondre mathématiquement aux données sources, sans perte de décimale ou de jour non justifiée.
- **SC-002** : Gain de temps : Le processus complet d'import et de création des brouillons doit s'exécuter de bout en bout en moins de 15 minutes pour un volume d'un mois de données.
- **SC-003** : Résilience : Le processus de facturation doit réussir dans 99.9% des cas de limites de requêtes (Rate Limiting) sans interruption brutale, grâce au backoff.
- **SC-004** : Traçabilité : 100% des runs (succès ou erreurs) doivent laisser une trace indélébile dans Cloud Logging et émettre <= 5 minutes après exécution une notification si action Finance requise.

## Assumptions

- Le référentiel client entre les outils sources (GCP, Napta) et l'outil cible (Sellsy) peut être réconcilié de manière certaine via une table de mappage ou un ID technique (ex: Cloud Channel ID), évitant le recours fragile aux chaînes de caractères.
- L'équipe métier accepte de vérifier manuellement les statuts "Brouillon" dans Sellsy, de nettoyer les doublons éventuels liés à un "re-run", et de régler les "clients inconnus" signalés par les alertes Slack/Chat.
- La logique spécifique de transformation (règles de marge, lookup du TJM) est considérée comme stable et définie dans la documentation métier initiale fournie.
