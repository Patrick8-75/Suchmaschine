"""
Gibt nur die Zeilen aus treffer.csv aus, die dem Nutzer noch nicht gezeigt wurden,
und aktualisiert danach den Merker in state/zuletzt_angezeigt.json.

Aufruf:
    python scripts/zeige_neue_treffer.py            # zeigt neue Treffer, markiert sie als gezeigt
    python scripts/zeige_neue_treffer.py --dry-run   # zeigt neue Treffer, OHNE den Merker zu aktualisieren
"""
import csv
import json
import sys
from pathlib import Path

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
TREFFER_CSV = PROJEKT_ROOT / "treffer.csv"
MARKER_DATEI = PROJEKT_ROOT / "state" / "zuletzt_angezeigt.json"


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    marker = json.loads(MARKER_DATEI.read_text(encoding="utf-8")) if MARKER_DATEI.exists() else {"gezeigte_zeilen": 0}
    gezeigte_zeilen = marker.get("gezeigte_zeilen", 0)

    with open(TREFFER_CSV, encoding="utf-8-sig", newline="") as f:
        alle_zeilen = list(csv.DictReader(f))

    neue = alle_zeilen[gezeigte_zeilen:]
    print(json.dumps(neue, ensure_ascii=False, indent=1))
    print(f"\n# {len(neue)} neue Zeile(n) seit letztem Anzeigen (von insgesamt {len(alle_zeilen)}).", file=sys.stderr)

    if not dry_run:
        marker["gezeigte_zeilen"] = len(alle_zeilen)
        MARKER_DATEI.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
