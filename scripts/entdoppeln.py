"""Entfernt doppelte Zeilen aus treffer.csv.

Eine Anzeige gilt als dieselbe, wenn die URL uebereinstimmt. Von mehreren
Zeilen zur selben URL bleibt die aelteste stehen (frueheste gefunden_am,
bei Gleichstand die weiter oben stehende) - so bleibt der urspruengliche
Fundzeitpunkt erhalten.

Ohne Argument nur Trockenlauf: zeigt an, was wegfiele, ohne die Datei
anzufassen. Erst `--apply` schreibt tatsaechlich; davor wird eine
Sicherungskopie treffer.csv.bak angelegt.

    python scripts/entdoppeln.py            # Trockenlauf
    python scripts/entdoppeln.py --apply    # tatsaechlich entdoppeln
"""

from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
TREFFER_CSV = PROJEKT_ROOT / "treffer.csv"
SICHERUNG = PROJEKT_ROOT / "treffer.csv.bak"

SPALTEN = ["gefunden_am", "portal", "suchbegriff", "titel", "preis", "ort",
           "inserat_datum", "baujahr", "betriebsstunden", "url"]


def lies_zeilen() -> list[dict]:
    with open(TREFFER_CSV, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def teile_auf(zeilen: list[dict]) -> tuple[list[dict], list[tuple[int, dict]]]:
    """Liefert (behalten, verwerfen) - verwerfen mit urspruenglicher Zeilennummer."""
    erste_pro_url: dict[str, int] = {}
    for i, z in enumerate(zeilen):
        url = z["url"]
        if url not in erste_pro_url:
            erste_pro_url[url] = i
        elif z["gefunden_am"] < zeilen[erste_pro_url[url]]["gefunden_am"]:
            erste_pro_url[url] = i

    behalten_idx = set(erste_pro_url.values())
    behalten = [z for i, z in enumerate(zeilen) if i in behalten_idx]
    verwerfen = [(i + 2, z) for i, z in enumerate(zeilen) if i not in behalten_idx]
    return behalten, verwerfen


def schreibe(zeilen: list[dict]) -> None:
    with open(TREFFER_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(SPALTEN)
        for z in zeilen:
            writer.writerow([z.get(s, "") for s in SPALTEN])


def main() -> None:
    anwenden = "--apply" in sys.argv
    zeilen = lies_zeilen()
    behalten, verwerfen = teile_auf(zeilen)

    print(f"treffer.csv: {len(zeilen)} Zeilen")
    print(f"  behalten:  {len(behalten)}")
    print(f"  entfernen: {len(verwerfen)}")

    if not verwerfen:
        print("\nKeine Dubletten gefunden - nichts zu tun.")
        return

    print("\nDiese Zeilen fielen weg (Zeilennummer in der Datei):")
    for nr, z in verwerfen:
        print(f"  Zeile {nr:4}  {z['gefunden_am']}  {z['portal']:20} {z['titel'][:42]}")

    if not anwenden:
        print("\nTROCKENLAUF - die Datei wurde nicht veraendert.")
        print("Zum tatsaechlichen Entdoppeln: python scripts/entdoppeln.py --apply")
        return

    shutil.copy2(TREFFER_CSV, SICHERUNG)
    schreibe(behalten)
    print(f"\nErledigt. Sicherungskopie der alten Fassung: {SICHERUNG.name}")


if __name__ == "__main__":
    main()
