"""
Maschinensuche P.Urny Handel - lokaler Suchlauf.

Durchsucht die aktiven Portale (config/portale.json) nach den hinterlegten
Suchbegriffen (config/suchbegriffe.json), vergleicht Treffer gegen bereits
gemeldete Anzeigen (state/gesehene_anzeigen.json) und trägt neue Treffer in
treffer.csv ein.

Wird von der Windows-Aufgabenplanung mehrmals täglich aufgerufen
(siehe register_task.ps1). Manueller Aufruf zum Testen:

    python scripts/maschinensuche_lokal.py
"""
from __future__ import annotations

import csv
import json
import logging
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from preis_utils import parse_preis_eur  # noqa: E402

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_SUCHBEGRIFFE = PROJEKT_ROOT / "config" / "suchbegriffe.json"
CONFIG_PORTALE = PROJEKT_ROOT / "config" / "portale.json"
STATE_DATEI = PROJEKT_ROOT / "state" / "gesehene_anzeigen.json"
TREFFER_CSV = PROJEKT_ROOT / "treffer.csv"
LOG_DATEI = PROJEKT_ROOT / "logs" / "lauf.log"
SPERR_DATEI = PROJEKT_ROOT / "state" / "suchlauf.lock"
SPERRE_MAX_ALTER_S = 30 * 60  # verwaiste Sperre (Absturz) nach 30 min ignorieren

MAX_IDS_PRO_PORTAL = 5000
HTTP_TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

LOG_DATEI.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DATEI, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------- Config/State

def lade_json(pfad: Path) -> dict:
    with open(pfad, encoding="utf-8") as f:
        return json.load(f)


def speichere_json(pfad: Path, daten: dict) -> None:
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- Baujahr/Betriebsstunden
# Best-effort-Extraktion aus dem Text, den die jeweilige Portal-Ergebnisliste ohnehin schon
# mitliefert (kein zusätzlicher Abruf der Detailseite je Anzeige). Liefert "", wenn das
# Portal an dieser Stelle nichts Passendes zeigt.

def extrahiere_baujahr(text: str) -> str:
    m = re.search(r"baujahr:?\s*(\d{4})\b", text, re.IGNORECASE)
    return m.group(1) if m else ""


def extrahiere_betriebsstunden(text: str) -> str:
    for muster in (
        r"betriebsstunden:?\s*([\d.,]+)\s*h\b",
        r"([\d.,]+)\s*bstd\.?",
        r"([\d.,]+)\s*m/std\.?",
        r"\b(\d{4}),\s*([\d.,]+)\s*h\b",  # Machinerypark: "2010, 12.888 h" ohne Label
    ):
        m = re.search(muster, text, re.IGNORECASE)
        if m:
            return m.groups()[-1] + " h"
    return ""


# ---------------------------------------------------------------- Portal-Scraper
# Jede Funktion bekommt einen Suchbegriff und liefert eine Liste von Treffern:
# {"titel": ..., "preis": ..., "ort": ..., "inserat_datum": ..., "url": ..., "id": ...}


def fetch_kleinanzeigen(suchbegriff: str) -> list[dict]:
    slug = urllib.parse.quote(suchbegriff.strip().lower().replace(" ", "-"))
    url = f"https://www.kleinanzeigen.de/s-{slug}/k0"
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")

    treffer = []
    for art in soup.find_all("article", class_="aditem"):
        adid = art.get("data-adid")
        href = art.get("data-href")
        if not adid or not href:
            continue
        titel_tag = art.select_one("h2.text-module-begin a")
        titel = titel_tag.get_text(strip=True) if titel_tag else ""
        preis_tag = art.select_one("p.aditem-main--middle--price-shipping--price")
        preis = preis_tag.get_text(strip=True) if preis_tag else ""
        ort_tag = art.select_one(".aditem-main--top--left")
        ort = ort_tag.get_text(strip=True) if ort_tag else ""
        datum_tag = art.select_one(".aditem-main--top--right")
        datum = datum_tag.get_text(strip=True) if datum_tag else ""
        beschreibung_tag = art.select_one(".aditem-main--middle--description")
        beschreibung_text = beschreibung_tag.get_text(" ", strip=True) if beschreibung_tag else ""
        baujahr = extrahiere_baujahr(titel + " " + beschreibung_text)
        betriebsstunden = extrahiere_betriebsstunden(titel + " " + beschreibung_text)
        treffer.append(
            {
                "id": adid,
                "titel": titel,
                "preis": preis,
                "ort": ort,
                "inserat_datum": datum,
                "baujahr": baujahr,
                "betriebsstunden": betriebsstunden,
                "url": "https://www.kleinanzeigen.de" + href,
            }
        )
    return treffer


def fetch_maschinensucher(suchbegriff: str) -> list[dict]:
    # Maschinensucher kommt mit mehrwortigen Modellbezeichnungen (z.B. "Takeuchi TB 145")
    # nicht zuverlässig klar und liefert dann irrelevante Treffer - nur das erste Wort
    # (i.d.R. die Marke) an die Portalsuche geben, die genaue Modell-Übereinstimmung
    # übernimmt hinterher passt_wirklich_zum_suchbegriff() anhand des vollen Suchbegriffs.
    suchwort_fuer_portal = suchbegriff.split()[0]
    url = "https://www.maschinensucher.de/main/search/index"
    params = {
        "search-word": suchwort_fuer_portal,
        "sort-field": "eintragsdatum",
        "sort-direction": "desc",
    }
    r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")

    treffer = []
    for card in soup.find_all("section", id=re.compile(r"^section-\d+-\d+$")):
        listing_id = card.get("data-listing-id")
        if not listing_id:
            continue
        titel_link = card.select_one('a[data-grid="title"]')
        titel = titel_link.get_text(" ", strip=True) if titel_link else ""
        href = titel_link.get("href") if titel_link else None
        preis_tag = card.select_one('div[data-grid="price"] span')
        preis = preis_tag.get_text(strip=True) if preis_tag else ""
        ort_tag = card.select_one(".country-name")
        ort = ort_tag.get_text(strip=True) if ort_tag else ""
        if not href:
            continue
        beschreibung_tag = card.select_one(".description-preview")
        beschreibung_text = beschreibung_tag.get_text(" ", strip=True) if beschreibung_tag else ""
        treffer.append(
            {
                "id": listing_id,
                "titel": titel,
                "preis": preis,
                "ort": ort,
                "inserat_datum": "",  # Maschinensucher zeigt kein Datum in der Trefferliste an
                "baujahr": extrahiere_baujahr(beschreibung_text),
                "betriebsstunden": extrahiere_betriebsstunden(beschreibung_text),
                "url": "https://www.maschinensucher.de" + href,
            }
        )
    return treffer


def fetch_machinerypark(suchbegriff: str) -> list[dict]:
    url = "https://de.machinerypark.com/suchen"
    params = {"search": suchbegriff, "result": "true"}
    r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")

    treffer = []
    for item in soup.find_all("section", class_="mpOfferItem"):
        titel_link = item.select_one("p.mb-3 a[href]")
        if not titel_link:
            continue
        href = titel_link.get("href")
        titel_tag = titel_link.find("strong")
        titel = titel_tag.get_text(strip=True) if titel_tag else titel_link.get_text(" ", strip=True)
        # Nach dem Titel folgt im selben Link-Block z.B. "2010, 12.888 h, gebraucht"
        rest_text = titel_link.get_text(" ", strip=True)
        if titel and rest_text.startswith(titel):
            rest_text = rest_text[len(titel):]
        preis_tag = item.select_one("strong.mpPrice")
        preis = preis_tag.get_text(strip=True) if preis_tag else ""
        ort_tag = item.select_one("small")
        ort = ort_tag.get_text(strip=True) if ort_tag else ""
        baujahr_match = re.match(r"\s*(\d{4})\s*,", rest_text)
        treffer.append(
            {
                "id": href,
                "titel": titel,
                "preis": preis,
                "ort": ort,
                "inserat_datum": "",
                "baujahr": baujahr_match.group(1) if baujahr_match else "",
                "betriebsstunden": extrahiere_betriebsstunden(rest_text),
                "url": "https://de.machinerypark.com" + href,
            }
        )
    return treffer


def _fetch_machineryline_familie(basis_url: str, suchbegriff: str) -> list[dict]:
    """Gemeinsame Scraper-Logik für machineryline.de und autoline.de - beide laufen
    auf derselben Plattform (identische Markup-Struktur)."""
    url = f"{basis_url}/search_text.php"
    r = requests.get(url, params={"query": suchbegriff}, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")

    treffer = []
    for item in soup.find_all("div", class_="sales-list-item"):
        code = item.get("data-code")
        titel_link = item.select_one("div.sl-item__title a")
        if not code or not titel_link:
            continue
        titel = titel_link.get_text(strip=True)
        href = titel_link.get("href")
        preis_tag = item.select_one("div.sl-item__price")
        preis = preis_tag.get_text(" ", strip=True) if preis_tag else ""
        ort_tag = item.select_one(".location-text")
        ort = ort_tag.get_text(strip=True) if ort_tag else ""
        eigenschaften_tag = item.select_one(".sl-main-props")
        eigenschaften_text = eigenschaften_tag.get_text(" ", strip=True) if eigenschaften_tag else ""
        treffer.append(
            {
                "id": code,
                "titel": titel,
                "preis": preis,
                "ort": ort,
                "inserat_datum": "",
                "baujahr": extrahiere_baujahr(eigenschaften_text),
                "betriebsstunden": extrahiere_betriebsstunden(eigenschaften_text),
                "url": href,
            }
        )
    return treffer


def fetch_machineryline(suchbegriff: str) -> list[dict]:
    return _fetch_machineryline_familie("https://machineryline.de", suchbegriff)


def fetch_autoline(suchbegriff: str) -> list[dict]:
    return _fetch_machineryline_familie("https://autoline.de", suchbegriff)


def fetch_tec24(suchbegriff: str) -> list[dict]:
    url = "https://de.tec24.com/suchergebnis.php"
    params = {"typ": suchbegriff, "ft_search": "1", "rewriting": "none"}
    r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")

    treffer = []
    for item in soup.find_all("div", class_="item-list"):
        titel_link = item.select_one("h5.add-title a")
        if not titel_link:
            continue
        href = titel_link.get("href")
        titel = titel_link.get_text(strip=True)

        # tec24 zeigt oft Brutto- UND Nettopreis getrennt an - Netto bevorzugen,
        # das war ja der Wunsch (klare Angabe statt Annahme).
        netto_tag = item.select_one("h3.item-price-small")
        brutto_tag = item.select_one("h2.item-price")
        preis = netto_tag.get_text(strip=True) if netto_tag else (
            brutto_tag.get_text(strip=True) if brutto_tag else ""
        )

        ort = ""
        kategorie_text = ""
        kategorie_tag = item.select_one("span.category")
        if kategorie_tag:
            kategorie_text = kategorie_tag.get_text(" ", strip=True)
            m = re.search(r"-\s*(\d{5}\s+.+)$", kategorie_text)
            if m:
                ort = m.group(1).strip()

        treffer.append(
            {
                "id": href,
                "titel": titel,
                "preis": preis,
                "ort": ort,
                "inserat_datum": "",
                "baujahr": extrahiere_baujahr(kategorie_text),
                "betriebsstunden": extrahiere_betriebsstunden(kategorie_text),
                "url": "https://de.tec24.com" + href if href.startswith("/") else href,
            }
        )
    return treffer


# Portalname -> Scraper-Funktion. Nur hier eintragen, was tatsächlich funktioniert
# (siehe config/portale.json "hinweis" für den Status der übrigen Portale).
SCRAPER = {
    "eBay Kleinanzeigen": fetch_kleinanzeigen,
    "Maschinensucher": fetch_maschinensucher,
    "Machinerypark": fetch_machinerypark,
    "Machineryline": fetch_machineryline,
    "Autoline": fetch_autoline,
    "tec24": fetch_tec24,
}


# ---------------------------------------------------------------- Ablauf

def gehoert_zu_ausschluss(titel: str, ausschluesse: list[str]) -> bool:
    titel_klein = titel.lower()
    return any(wort.lower() in titel_klein for wort in ausschluesse)


# Erkennungswörter für Ersatz-/Verschleißteile statt kompletter Maschinen (Nutzerwunsch
# 22.08.2026: "Ersatzteile oder Verschleissteile nicht anzeigen oder suchen, nur komplette
# Maschine!"). Bewusst mehrteilige/eindeutige Begriffe, damit z.B. "Kettenbagger" nicht wegen
# "Kette" fälschlich rausfliegt, und KEINE Begriffe wie "Schneidwerk"/"Pflücker"/"Vorsatz", die
# selbst komplette, gesuchte Anbaugeräte bezeichnen (z.B. Claas Conspeed/Geringhoff sind
# Erntevorsätze - die sollen ja gerade gefunden werden). Aus dem gleichen Grund stehen hier
# "tieflöffel"/"baggerlöffel" statt eines pauschalen "löffel": komplette Bagger werden oft
# mitsamt Löffel angeboten ("Powertilt+Löffel nur 1957h") und dürfen nicht rausfallen.
ERSATZTEIL_BEGRIFFE = [
    "ersatzteil", "verschleißteil", "verschleissteil", "gummikette", "laufrolle", "tragrolle",
    "stützrolle", "spannrolle", "leitrad", "kettenrad", "antriebsrad", "fahrantrieb", "fahrmotor",
    "endantrieb", "finale drive", "hydraulikpumpe", "zahnradpumpe", "vorsteuergerät", "türschloss",
    "türverriegelung", "türe kpl", "sitzpolster", "sitzkissen", "löffelbolzen", "reparatursatz",
    "for parts", "radsatz", "breitreifen", "wechsler", "kettenlaufwerksrolle",
    "tieflöffel", "tiefloeffel", "baggerlöffel", "baggerloeffel", "lichtmaschine",
    "buchsen/bolzen", "roata de ghidaj", "rola intinzatoare", "role de rulare", "senila pentru",
    "kettenlaufrolle", "winkelgetriebe", "getriebe", "pflückeinheit", "häckslerarm",
    "keilriemen", "zahnriemen", "dichtung", "bremsbelag", "kupplung", "hydraulikschlauch",
    "achse", "verschleißteile", "verschleissteile", "häckslermesser", "lagermaisschnecke",
    "teile", "ersatzkette", "warntafel", "haube", "spitze", "adaption", "pflückerkette",
]

# "Kette"/"Ketten" als eigenständiges Wort (z.B. "Maispflücker Ketten 00...") ist ein
# Ersatzteil - aber als Teil eines zusammengesetzten Worts wie "Kettenbagger" (komplette
# Baumaschine!) nicht. \b matcht hier nicht innerhalb von Komposita ohne Leerzeichen davor,
# daher reicht ein einfacher Wortgrenzen-Regex statt einer Ausnahmeliste.
ERSATZTEIL_GANZWORT_REGEX = re.compile(r"\bketten?\b")


def ist_ersatzteil(titel: str) -> bool:
    titel_klein = titel.lower()
    if any(begriff in titel_klein for begriff in ERSATZTEIL_BEGRIFFE):
        return True
    return bool(ERSATZTEIL_GANZWORT_REGEX.search(titel_klein))


# Mietmaschinen statt Kaufangebote (Nutzerwunsch 22.08.2026: "keine Mietmaschinen
# anzeigen"). Bei Machineryline steht das oft nur im URL-Pfad (/-/Miete/...), nicht
# im Titel selbst - deshalb wird hier zusätzlich die URL geprüft.
MIETE_BEGRIFFE = [
    "miete", "mieten", "vermietung", "vermieten", "zu vermieten", "leihmaschine",
    "mietmaschine", "leasing", "rental",
]
MIETE_URL_SEGMENT_REGEX = re.compile(r"/miete/", re.IGNORECASE)


def ist_mietmaschine(titel: str, url: str) -> bool:
    titel_klein = titel.lower()
    if any(begriff in titel_klein for begriff in MIETE_BEGRIFFE):
        return True
    return bool(MIETE_URL_SEGMENT_REGEX.search(url or ""))


def normalisiere_fuer_abgleich(text: str) -> str:
    """Buchstabe+Zahl-Grenzen mit Leerzeichen/Bindestrich dazwischen zusammenziehen,
    damit z.B. 'TB 145' und 'TB145' beim Abgleich als gleich gelten."""
    text = text.lower()
    text = re.sub(r"(?<=[a-zäöü])[\s\-]+(?=\d)", "", text)
    text = re.sub(r"(?<=\d)[\s\-]+(?=[a-zäöü])", "", text)
    return text


def passt_wirklich_zum_suchbegriff(titel: str, suchbegriff: str) -> bool:
    """Manche Portale (z.B. Maschinensucher) suchen unscharf ('enthält irgendeins
    der Wörter') statt nach der genauen Phrase. Hier alle Wörter des Suchbegriffs
    verlangen, damit z.B. bei 'Claas Conspeed' nicht jede beliebige Claas-Anzeige
    durchrutscht - und Modellbezeichnungen wie 'TB 145'/'TB145' werden vor dem
    Abgleich vereinheitlicht."""
    titel_norm = normalisiere_fuer_abgleich(titel)
    woerter = [w for w in re.split(r"\s+", normalisiere_fuer_abgleich(suchbegriff)) if w]
    return all(w in titel_norm for w in woerter)


def erfuellt_zusatzfilter(titel: str, erfordert_eines_von: list[str] | None) -> bool:
    """Bei breiten Markensuchen (z.B. nur 'Claas' statt 'Claas Conspeed') muss zusätzlich
    mindestens eines der in 'erfordert_eines_von' hinterlegten Wörter im Titel stehen,
    damit nicht jede beliebige Anzeige der Marke durchrutscht (Traktoren, Mähdrescher, ...)."""
    if not erfordert_eines_von:
        return True
    titel_klein = titel.lower()
    return any(wort.lower() in titel_klein for wort in erfordert_eines_von)


def hole_neue_treffer(
    portal_name: str,
    suchbegriff: str,
    gesehen: set[str],
    ausschluesse: list[str],
    erfordert_eines_von: list[str] | None = None,
) -> list[dict]:
    scraper = SCRAPER.get(portal_name)
    if scraper is None:
        log.info("Portal '%s' hat (noch) keinen lokalen Scraper - übersprungen.", portal_name)
        return []
    try:
        rohtreffer = scraper(suchbegriff)
    except Exception as exc:  # Portal down, Struktur geändert, Netzwerkfehler, ...
        log.warning("Fehler bei %s / '%s': %s", portal_name, suchbegriff, exc)
        return []

    neue = []
    for t in rohtreffer:
        if not passt_wirklich_zum_suchbegriff(t["titel"], suchbegriff):
            continue
        if not erfuellt_zusatzfilter(t["titel"], erfordert_eines_von):
            continue
        if gehoert_zu_ausschluss(t["titel"], ausschluesse):
            continue
        if ist_ersatzteil(t["titel"]):
            continue
        if ist_mietmaschine(t["titel"], t["url"]):
            continue
        if parse_preis_eur(t["preis"]) is None:
            continue  # kein erkennbarer Preis (z.B. "Preis auf Anfrage", "VB" allein) - Nutzerwunsch
        if t["id"] in gesehen:
            continue
        neue.append(t)
    return neue


def sperre_setzen() -> bool:
    """Legt die Sperrdatei an. False, wenn bereits ein Lauf aktiv ist.

    Hintergrund (04.09.2026): Drei innerhalb von 38 s gestartete Laeufe haben
    dieselben Anzeigen je dreimal in treffer.csv eingetragen, weil der State
    erst am Laufende geschrieben wird. Die Sperre verhindert Parallellaeufe;
    eine verwaiste Sperre (Absturz, Stromausfall) wird nach 30 min ignoriert.
    """
    import os
    import time

    if SPERR_DATEI.exists():
        alter = time.time() - SPERR_DATEI.stat().st_mtime
        if alter < SPERRE_MAX_ALTER_S:
            return False
        log.warning("Verwaiste Sperrdatei (%.0f min alt) wird ersetzt.", alter / 60)
        SPERR_DATEI.unlink(missing_ok=True)
    SPERR_DATEI.parent.mkdir(exist_ok=True)
    SPERR_DATEI.write_text(f"pid={os.getpid()}\n", encoding="utf-8")
    return True


def sperre_freigeben() -> None:
    SPERR_DATEI.unlink(missing_ok=True)


def bereits_erfasste_urls() -> set[str]:
    """URLs, die schon in treffer.csv stehen - zweites Netz gegen Dubletten."""
    if not TREFFER_CSV.exists():
        return set()
    with open(TREFFER_CSV, newline="", encoding="utf-8-sig") as f:
        return {z["url"] for z in csv.DictReader(f) if z.get("url")}


def haenge_an_csv_an(zeilen: list[dict]) -> None:
    neu_anlegen = not TREFFER_CSV.exists()
    with open(TREFFER_CSV, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if neu_anlegen:
            writer.writerow(
                ["gefunden_am", "portal", "suchbegriff", "titel", "preis", "ort", "inserat_datum",
                 "baujahr", "betriebsstunden", "url"]
            )
        for z in zeilen:
            writer.writerow(
                [z["gefunden_am"], z["portal"], z["suchbegriff"], z["titel"], z["preis"], z["ort"],
                 z["inserat_datum"], z.get("baujahr", ""), z.get("betriebsstunden", ""), z["url"]]
            )


def git_commit_und_push() -> None:
    import subprocess

    try:
        subprocess.run(["git", "add", "treffer.csv", "state/gesehene_anzeigen.json"], cwd=PROJEKT_ROOT, check=True)
        status = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=PROJEKT_ROOT
        )
        if status.returncode == 0:
            return  # keine Änderungen
        zeitstempel = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        subprocess.run(
            ["git", "commit", "-q", "-m", f"Automatischer lokaler Lauf {zeitstempel}"],
            cwd=PROJEKT_ROOT,
            check=True,
        )
        subprocess.run(["git", "push", "-q"], cwd=PROJEKT_ROOT, check=True)
    except Exception as exc:
        log.warning("Git commit/push übersprungen (kein Problem für den Suchlauf selbst): %s", exc)


def main() -> None:
    LOG_DATEI.parent.mkdir(exist_ok=True)
    if not sperre_setzen():
        log.info("Suchlauf uebersprungen: es laeuft bereits ein anderer (state/suchlauf.lock).")
        return
    try:
        _suchlauf()
    finally:
        sperre_freigeben()


def _suchlauf() -> None:
    log.info("=== Suchlauf gestartet ===")

    suchbegriffe_cfg = lade_json(CONFIG_SUCHBEGRIFFE)
    portale_cfg = lade_json(CONFIG_PORTALE)
    state = lade_json(STATE_DATEI)
    state.setdefault("portale", {})

    suchbegriffe = suchbegriffe_cfg["suchbegriffe"]
    ausschluesse = suchbegriffe_cfg.get("ausschluesse", {}).get("global", [])

    jetzt = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schon_in_csv = bereits_erfasste_urls()
    alle_neuen_zeilen = []
    zusammenfassung = []

    for portal in portale_cfg["portale"]:
        if not portal.get("aktiv"):
            continue
        name = portal["name"]
        portal_gruppen = portal.get("gruppen") or []  # leer = alle Gruppen
        gesehen = set(state["portale"].get(name, []))
        neu_fuer_portal = 0

        passende_suchbegriffe = [
            s for s in suchbegriffe if not portal_gruppen or s["gruppe"] in portal_gruppen
        ]
        for eintrag in passende_suchbegriffe:
            suchbegriff = eintrag["begriff"]
            neue = hole_neue_treffer(name, suchbegriff, gesehen, ausschluesse, eintrag.get("erfordert_eines_von"))
            for t in neue:
                if t["url"] in schon_in_csv:
                    # Anzeige steht schon in treffer.csv (z.B. ueber ein
                    # Schwesterportal oder einen frueheren Lauf) - nur als
                    # gesehen markieren, nicht erneut eintragen.
                    gesehen.add(t["id"])
                    continue
                schon_in_csv.add(t["url"])
                alle_neuen_zeilen.append(
                    {
                        "gefunden_am": jetzt,
                        "portal": name,
                        "suchbegriff": suchbegriff,
                        "titel": t["titel"],
                        "preis": t["preis"],
                        "ort": t["ort"],
                        "inserat_datum": t["inserat_datum"],
                        "baujahr": t.get("baujahr", ""),
                        "betriebsstunden": t.get("betriebsstunden", ""),
                        "url": t["url"],
                    }
                )
                gesehen.add(t["id"])
                neu_fuer_portal += 1

        if neu_fuer_portal or name in SCRAPER:
            state["portale"][name] = list(gesehen)[-MAX_IDS_PRO_PORTAL:]
        zusammenfassung.append(f"{name}: {neu_fuer_portal} neue Treffer")

    if alle_neuen_zeilen:
        haenge_an_csv_an(alle_neuen_zeilen)
        speichere_json(STATE_DATEI, state)
        git_commit_und_push()
    else:
        log.info("Keine neuen Treffer in diesem Lauf.")

    log.info("Zusammenfassung: %s", " | ".join(zusammenfassung))
    log.info("=== Suchlauf beendet: %d neue(r) Treffer insgesamt ===", len(alle_neuen_zeilen))


if __name__ == "__main__":
    main()
