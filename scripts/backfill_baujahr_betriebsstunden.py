"""
Einmaliger Nachtrag: ruft für jede Zeile in treffer.csv, die noch kein Baujahr UND keine
Betriebsstunden hat, die Detailseite der Anzeige auf und versucht, beides aus dem
Volltext der Seite zu extrahieren (funktioniert portalübergreifend, da Baujahr/
Betriebsstunden auf den meisten Detailseiten als lesbarer Text irgendwo auftauchen).

Nicht mehr erreichbare Anzeigen (verkauft/gelöscht, 404 o.ä.) werden übersprungen,
bleiben aber unverändert in treffer.csv stehen (kein Datenverlust).

Aufruf:
    python scripts/backfill_baujahr_betriebsstunden.py
"""
import csv
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maschinensuche_lokal import USER_AGENT, HTTP_TIMEOUT, extrahiere_baujahr, extrahiere_betriebsstunden  # noqa: E402

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
TREFFER_CSV = PROJEKT_ROOT / "treffer.csv"
WARTEZEIT_SEC = 0.4


def hole_baujahr_betriebsstunden_von_detailseite(url: str) -> tuple[str, str]:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)
        if r.status_code != 200:
            return "", ""
        r.encoding = "utf-8"
        text = BeautifulSoup(r.text, "lxml").get_text(" ", strip=True)
        return extrahiere_baujahr(text), extrahiere_betriebsstunden(text)
    except Exception:
        return "", ""


def main() -> None:
    with open(TREFFER_CSV, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
        feldnamen = list(rows[0].keys()) if rows else []

    zu_pruefen = [r for r in rows if not r.get("baujahr") and not r.get("betriebsstunden")]
    print(f"{len(zu_pruefen)} von {len(rows)} Zeilen ohne Baujahr/Betriebsstunden - rufe Detailseiten ab ...")

    aktualisiert = 0
    for i, r in enumerate(zu_pruefen, 1):
        baujahr, betriebsstunden = hole_baujahr_betriebsstunden_von_detailseite(r["url"])
        if baujahr or betriebsstunden:
            r["baujahr"] = baujahr
            r["betriebsstunden"] = betriebsstunden
            aktualisiert += 1
        if i % 20 == 0 or i == len(zu_pruefen):
            print(f"  {i}/{len(zu_pruefen)} geprüft, {aktualisiert} aktualisiert ...")
        time.sleep(WARTEZEIT_SEC)

    with open(TREFFER_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=feldnamen)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Fertig: {aktualisiert} von {len(zu_pruefen)} Zeilen mit Baujahr/Betriebsstunden ergänzt.")


if __name__ == "__main__":
    main()
