#!/usr/bin/env python3
"""
Outil d'initialisation du mapping Napta → Sellsy.

Récupère tous les clients uniques côté Napta (project.client)
et toutes les companies côté Sellsy, puis propose un mapping
automatique par fuzzy matching (difflib).

Génère un CSV pour que la Finance puisse :
- Valider les matchs automatiques (score > seuil)
- Compléter les matchs manquants par couper-coller

Usage:
    python tools/init_client_mapping.py
    python tools/init_client_mapping.py --start 2026-01-01 --end 2026-03-31 --threshold 0.5
"""
import argparse
import csv
import sys
import os
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from connectors.napta_client import NaptaClient
from connectors.sellsy_client import SellsyClient
from core.logger import app_logger
import requests


def fetch_all_sellsy_companies(client: SellsyClient) -> List[Dict]:
    """Récupère toutes les companies Sellsy (paginé)."""
    all_companies = []
    offset = 0
    while True:
        params = {"limit": 100, "offset": offset}
        r = requests.get(
            f"{client.base_url}/companies",
            headers=client._get_headers(),
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        companies = data.get("data", [])
        all_companies.extend(companies)
        pagination = data.get("pagination", {})
        if len(companies) < 100:
            break
        offset += 100
    return all_companies


def fetch_napta_client_names(napta: NaptaClient, start: str, end: str) -> Tuple[Dict[str, int], Dict[str, List[int]]]:
    """
    Récupère les noms de clients Napta uniques à partir des projets
    ayant des time entries validées sur la période.
    Retourne (client_counts, client_project_ids) :
      - { client_name: nb_projets }
      - { client_name: [project_napta_id, ...] }
    """
    app_logger.info(f"Extraction time entries Napta {start} → {end}...")
    entries = napta.fetch_validated_time_entries(start, end)
    if not entries:
        app_logger.warning("Aucune time entry.")
        return {}, {}

    project_ids = list({
        (te.get("project") or {}).get("napta_id")
        for te in entries
        if (te.get("project") or {}).get("napta_id")
    })
    app_logger.info(f"{len(entries)} time entries, {len(project_ids)} projets uniques")

    projects = napta.fetch_projects(project_ids)

    client_counts: Dict[str, int] = {}
    client_project_ids: Dict[str, List[int]] = {}
    for p in projects:
        name = (p.get("client") or "").strip()
        pid = (p.get("id") or {}).get("napta_id")
        if name and pid:
            client_counts[name] = client_counts.get(name, 0) + 1
            if name not in client_project_ids:
                client_project_ids[name] = []
            client_project_ids[name].append(pid)

    return client_counts, client_project_ids


def normalize(name: str) -> str:
    """Normalise un nom pour le fuzzy matching."""
    import unicodedata
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode()
    return name.lower().strip()


def fuzzy_match(
    napta_names: List[str],
    sellsy_companies: List[Dict],
    threshold: float = 0.45,
) -> List[Tuple[str, int, str, str, float]]:
    """
    Pour chaque client Napta, trouve le meilleur match Sellsy par similarité.
    Retourne [(napta_name, sellsy_id, sellsy_name, sellsy_type, score)].
    """
    results = []
    for napta_name in sorted(napta_names):
        norm_napta = normalize(napta_name)
        best_score = 0.0
        best_company = None

        for company in sellsy_companies:
            sellsy_name = company.get("name", "")
            norm_sellsy = normalize(sellsy_name)

            score = SequenceMatcher(None, norm_napta, norm_sellsy).ratio()

            # Bonus si un nom est contenu dans l'autre
            if norm_napta in norm_sellsy or norm_sellsy in norm_napta:
                score = max(score, 0.85)

            if score > best_score:
                best_score = score
                best_company = company

        if best_company and best_score >= threshold:
            results.append((
                napta_name,
                best_company["id"],
                best_company.get("name", ""),
                best_company.get("type", ""),
                round(best_score, 2),
            ))
        else:
            results.append((napta_name, None, "", "", 0.0))

    return results


def generate_csv(
    matches: List[Tuple],
    napta_counts: Dict[str, int],
    napta_project_ids: Dict[str, List[int]],
    sellsy_companies: List[Dict],
    output_path: str,
):
    """
    Génère le CSV de mapping avec 3 sections :
    1. Mapping proposé (fuzzy)
    2. Clients Napta sans match (à remplir à la main)
    3. Référentiel Sellsy complet (pour couper-coller)
    """
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")

        # ── Section 1 : Mapping proposé ──
        writer.writerow(["=== MAPPING PROPOSE (à valider / corriger) ==="])
        writer.writerow([
            "napta_client_name",
            "napta_nb_projets",
            "sellsy_company_id",
            "sellsy_company_name",
            "sellsy_type",
            "match_score",
            "VALIDE (oui/non)",
            "napta_project_ids",
        ])

        matched = [m for m in matches if m[1] is not None]
        unmatched = [m for m in matches if m[1] is None]

        for napta_name, sid, sname, stype, score in sorted(matched, key=lambda x: -x[4]):
            pids = "|".join(str(i) for i in napta_project_ids.get(napta_name, []))
            writer.writerow([
                napta_name,
                napta_counts.get(napta_name, 0),
                sid or "",
                sname,
                stype,
                score,
                "oui" if score >= 0.8 else "",
                pids,
            ])

        # ── Section 2 : Non matchés ──
        writer.writerow([])
        writer.writerow(["=== CLIENTS NAPTA SANS MATCH (à remplir à la main) ==="])
        writer.writerow([
            "napta_client_name",
            "napta_nb_projets",
            "sellsy_company_id",
            "sellsy_company_name",
            "sellsy_type",
            "match_score",
            "VALIDE (oui/non)",
            "napta_project_ids",
        ])

        for napta_name, _, _, _, _ in sorted(unmatched, key=lambda x: -napta_counts.get(x[0], 0)):
            pids = "|".join(str(i) for i in napta_project_ids.get(napta_name, []))
            writer.writerow([
                napta_name,
                napta_counts.get(napta_name, 0),
                "",
                "",
                "",
                "",
                "",
                pids,
            ])

        # ── Section 3 : Référentiel Sellsy ──
        writer.writerow([])
        writer.writerow(["=== REFERENTIEL SELLSY COMPLET (pour copier-coller ID/nom) ==="])
        writer.writerow(["sellsy_company_id", "sellsy_company_name", "sellsy_type"])

        for c in sorted(sellsy_companies, key=lambda x: x.get("name", "")):
            writer.writerow([c["id"], c.get("name", ""), c.get("type", "")])


def main():
    parser = argparse.ArgumentParser(description="Initialise le mapping client Napta → Sellsy")
    parser.add_argument("--start", default="2026-01-01", help="Début période Napta (YYYY-MM-DD)")
    parser.add_argument("--end", default="2026-03-31", help="Fin période Napta (YYYY-MM-DD)")
    parser.add_argument("--threshold", type=float, default=0.45, help="Seuil fuzzy matching (0-1)")
    parser.add_argument("--output", default="mapping_napta_sellsy.csv", help="Fichier CSV de sortie")
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"  Mapping Napta → Sellsy")
    print(f"  Période Napta : {args.start} → {args.end}")
    print(f"  Seuil fuzzy   : {args.threshold}")
    print(f"  Sortie        : {args.output}")
    print(f"{'='*60}")

    # 1. Récupérer les companies Sellsy
    print("\n[1/4] Chargement des companies Sellsy...")
    sellsy = SellsyClient()
    sellsy_companies = fetch_all_sellsy_companies(sellsy)
    client_type = [c for c in sellsy_companies if c.get("type") == "client"]
    print(f"       {len(sellsy_companies)} companies ({len(client_type)} clients, "
          f"{len(sellsy_companies) - len(client_type)} prospects/autres)")

    # 2. Récupérer les noms de clients Napta
    print("\n[2/4] Extraction des clients Napta (time entries validées)...")
    napta = NaptaClient()
    napta_counts, napta_project_ids = fetch_napta_client_names(napta, args.start, args.end)
    print(f"       {len(napta_counts)} clients Napta uniques")

    if not napta_counts:
        print("\nAucun client Napta trouvé. Vérifiez la période.")
        return

    # 3. Fuzzy matching
    print(f"\n[3/4] Fuzzy matching (seuil={args.threshold})...")
    matches = fuzzy_match(list(napta_counts.keys()), sellsy_companies, args.threshold)
    matched_count = sum(1 for m in matches if m[1] is not None)
    auto_valid = sum(1 for m in matches if m[4] >= 0.8)
    print(f"       {matched_count}/{len(matches)} matchés (dont {auto_valid} auto-validés >= 0.8)")

    # 4. Générer le CSV
    print(f"\n[4/4] Génération du CSV → {args.output}")
    generate_csv(matches, napta_counts, napta_project_ids, sellsy_companies, args.output)
    print(f"       Fichier créé : {os.path.abspath(args.output)}")

    # Résumé
    print(f"\n{'='*60}")
    print(f"  RÉSUMÉ")
    print(f"  Clients Napta   : {len(napta_counts)}")
    print(f"  Matchés auto    : {matched_count}")
    print(f"  Auto-validés    : {auto_valid} (score >= 0.8)")
    print(f"  À mapper à la main : {len(matches) - matched_count}")
    print(f"{'='*60}")
    print(f"\nOuvrez {args.output} dans Excel, validez/corrigez les matchs,")
    print(f"puis copiez les IDs Sellsy depuis la section référentiel.")


if __name__ == "__main__":
    main()
