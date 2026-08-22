"""
Gibt nur die Zeilen aus treffer.csv aus, die dem Nutzer noch nicht gezeigt wurden UND
in den letzten 24 Stunden gefunden wurden, und aktualisiert danach den Merker in
state/zuletzt_angezeigt.json. Ältere, noch nicht gezeigte Zeilen gelten als abgelaufen
und werden übersprungen (der Merker rückt trotzdem bis ans Ende vor, damit sie später
nicht doch noch auftauchen).

Aufruf:
    python scripts/zeige_neue_treffer.py            # zeigt neue Treffer, markiert alles bis dahin als gezeigt
    python scripts/zeige_neue_treffer.py --dry-run   # zeigt neue Treffer, OHNE den Merker zu aktualisieren
"""
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
TREFFER_CSV = PROJEKT_ROOT / "treffer.csv"
MARKER_DATEI = PROJEKT_ROOT / "state" / "zuletzt_angezeigt.json"

ANZEIGE_FENSTER = timedelta(hours=24)


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    marker = json.loads(MARKER_DATEI.read_text(encoding="utf-8")) if MARKER_DATEI.exists() else {"gezeigte_zeilen": 0}
    gezeigte_zeilen = marker.get("gezeigte_zeilen", 0)

    with open(TREFFER_CSV, encoding="utf-8-sig", newline="") as f:
        alle_zeilen = list(csv.DictReader(f))

    ungezeigt = alle_zeilen[gezeigte_zeilen:]

    grenze = datetime.now(timezone.utc) - ANZEIGE_FENSTER
    aktuell, abgelaufen = [], 0
    for z in ungezeigt:
        try:
            gefunden_am = datetime.strptime(z["gefunden_am"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            aktuell.append(z)  # kein/ungültiges Datum -> lieber zeigen als verlieren
            continue
        if gefunden_am >= grenze:
            aktuell.append(z)
        else:
            abgelaufen += 1

    print(json.dumps(aktuell, ensure_ascii=False, indent=1))
    print(
        f"\n# {len(aktuell)} neue Zeile(n) innerhalb der letzten 24h (von {len(ungezeigt)} ungezeigten, "
        f"{abgelaufen} davon älter als 24h und daher übersprungen; insgesamt {len(alle_zeilen)} Zeilen).",
        file=sys.stderr,
    )

    if not dry_run:
        marker["gezeigte_zeilen"] = len(alle_zeilen)
        MARKER_DATEI.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
