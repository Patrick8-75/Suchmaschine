"""
Maschinensuche P.Urny Handel - lokaler Suchlauf.

Durchsucht die aktiven Portale (config/portale.json) nach den hinterlegten
Suchbegriffen (config/suchbegriffe.json), vergleicht Treffer gegen bereits
gemeldete Anzeigen (state/gesehene_anzeigen.json) und trägt neue Treffer in
treffer.csv ein. Verschickt bei neuen Treffern eine E-Mail (SMTP-Zugangsdaten
kommen aus dem Windows Credential Manager, siehe setup_email_zugangsdaten.py).

Wird von der Windows-Aufgabenplanung mehrmals täglich aufgerufen
(siehe register_task.ps1). Manueller Aufruf zum Testen:

    python scripts/maschinensuche_lokal.py
"""
from __future__ import annotations

import csv
import json
import logging
import re
import smtplib
import sys
import urllib.parse
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_SUCHBEGRIFFE = PROJEKT_ROOT / "config" / "suchbegriffe.json"
CONFIG_PORTALE = PROJEKT_ROOT / "config" / "portale.json"
STATE_DATEI = PROJEKT_ROOT / "state" / "gesehene_anzeigen.json"
TREFFER_CSV = PROJEKT_ROOT / "treffer.csv"
LOG_DATEI = PROJEKT_ROOT / "logs" / "lauf.log"

MAX_IDS_PRO_PORTAL = 5000
HTTP_TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

KEYRING_SERVICE = "purny-handel-maschinensuche-smtp"

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
        treffer.append(
            {
                "id": adid,
                "titel": titel,
                "preis": preis,
                "ort": ort,
                "inserat_datum": datum,
                "url": "https://www.kleinanzeigen.de" + href,
            }
        )
    return treffer


def fetch_maschinensucher(suchbegriff: str) -> list[dict]:
    url = "https://www.maschinensucher.de/main/search/index"
    params = {
        "search-word": suchbegriff,
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
        treffer.append(
            {
                "id": listing_id,
                "titel": titel,
                "preis": preis,
                "ort": ort,
                "inserat_datum": "",  # Maschinensucher zeigt kein Datum in der Trefferliste an
                "url": "https://www.maschinensucher.de" + href,
            }
        )
    return treffer


# Portalname -> Scraper-Funktion. Nur hier eintragen, was tatsächlich funktioniert
# (siehe config/portale.json "hinweis" für den Status der übrigen Portale).
SCRAPER = {
    "eBay Kleinanzeigen": fetch_kleinanzeigen,
    "Maschinensucher": fetch_maschinensucher,
}


# ---------------------------------------------------------------- Ablauf

def gehoert_zu_ausschluss(titel: str, ausschluesse: list[str]) -> bool:
    titel_klein = titel.lower()
    return any(wort.lower() in titel_klein for wort in ausschluesse)


def hole_neue_treffer(portal_name: str, suchbegriff: str, gesehen: set[str], ausschluesse: list[str]) -> list[dict]:
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
        if gehoert_zu_ausschluss(t["titel"], ausschluesse):
            continue
        if t["id"] in gesehen:
            continue
        neue.append(t)
    return neue


def haenge_an_csv_an(zeilen: list[dict]) -> None:
    neu_anlegen = not TREFFER_CSV.exists()
    with open(TREFFER_CSV, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if neu_anlegen:
            writer.writerow(
                ["gefunden_am", "portal", "suchbegriff", "titel", "preis", "ort", "inserat_datum", "url"]
            )
        for z in zeilen:
            writer.writerow(
                [z["gefunden_am"], z["portal"], z["suchbegriff"], z["titel"], z["preis"], z["ort"], z["inserat_datum"], z["url"]]
            )


def sende_email(neue_zeilen: list[dict]) -> None:
    try:
        import keyring
    except ImportError:
        log.warning("Paket 'keyring' nicht installiert - E-Mail-Versand übersprungen.")
        return

    benutzer = keyring.get_password(KEYRING_SERVICE, "smtp_username")
    passwort = keyring.get_password(KEYRING_SERVICE, "smtp_password")
    if not benutzer or not passwort:
        log.info(
            "Keine SMTP-Zugangsdaten im Windows Credential Manager hinterlegt "
            "(einmalig python scripts/setup_email_zugangsdaten.py ausführen) - E-Mail-Versand übersprungen."
        )
        return

    empfaenger = "info@urny-handel.com"
    betreff = f"{len(neue_zeilen)} neue Maschinenangebote - P.Urny Handel"
    zeilen_text = "\n\n".join(
        f"- [{z['portal']}] {z['titel']}\n"
        f"  Suchbegriff: {z['suchbegriff']} | Preis: {z['preis']} | Ort: {z['ort']}\n"
        f"  {z['url']}"
        for z in neue_zeilen
    )
    body = f"{len(neue_zeilen)} neue Anzeige(n) gefunden:\n\n{zeilen_text}\n"

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = betreff
    msg["From"] = benutzer
    msg["To"] = empfaenger

    try:
        with smtplib.SMTP("smtp.office365.com", 587, timeout=30) as server:
            server.starttls()
            server.login(benutzer, passwort)
            server.sendmail(benutzer, [empfaenger], msg.as_string())
        log.info("E-Mail mit %d neuen Treffern an %s verschickt.", len(neue_zeilen), empfaenger)
    except Exception as exc:
        log.error("E-Mail-Versand fehlgeschlagen: %s", exc)


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
    log.info("=== Suchlauf gestartet ===")

    suchbegriffe_cfg = lade_json(CONFIG_SUCHBEGRIFFE)
    portale_cfg = lade_json(CONFIG_PORTALE)
    state = lade_json(STATE_DATEI)
    state.setdefault("portale", {})

    suchbegriffe = suchbegriffe_cfg["suchbegriffe"]
    ausschluesse = suchbegriffe_cfg.get("ausschluesse", {}).get("global", [])

    jetzt = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    alle_neuen_zeilen = []
    zusammenfassung = []

    for portal in portale_cfg["portale"]:
        if not portal.get("aktiv"):
            continue
        name = portal["name"]
        gesehen = set(state["portale"].get(name, []))
        neu_fuer_portal = 0

        for suchbegriff in suchbegriffe:
            neue = hole_neue_treffer(name, suchbegriff, gesehen, ausschluesse)
            for t in neue:
                alle_neuen_zeilen.append(
                    {
                        "gefunden_am": jetzt,
                        "portal": name,
                        "suchbegriff": suchbegriff,
                        "titel": t["titel"],
                        "preis": t["preis"],
                        "ort": t["ort"],
                        "inserat_datum": t["inserat_datum"],
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
        sende_email(alle_neuen_zeilen)
        git_commit_und_push()
    else:
        log.info("Keine neuen Treffer in diesem Lauf.")

    log.info("Zusammenfassung: %s", " | ".join(zusammenfassung))
    log.info("=== Suchlauf beendet: %d neue(r) Treffer insgesamt ===", len(alle_neuen_zeilen))


if __name__ == "__main__":
    main()
