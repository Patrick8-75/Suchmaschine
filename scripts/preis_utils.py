"""Gemeinsame Preis-Hilfsfunktion für maschinensuche_lokal.py und render_radar.py."""
import re


def parse_preis_eur(preis: str) -> float | None:
    """Extrahiert den ersten erkennbaren Euro-Betrag aus einem Preis-String.
    Gibt None zurück, wenn kein Betrag erkennbar ist (z.B. "VB" allein,
    "Preis auf Anfrage", "Versteigerung")."""
    # (?!\w) statt \b: \b matcht nach "€" nicht (€ ist kein Wortzeichen, und am
    # Stringende gibt es dann keine Wortgrenze) - dadurch wuerden sonst ALLE
    # Preise mit "€"-Symbol (statt "EUR") faelschlich als nicht erkennbar gelten.
    m = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*(?:€|EUR)(?!\w)", preis or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(".", "").replace(",", "."))
    except ValueError:
        return None
