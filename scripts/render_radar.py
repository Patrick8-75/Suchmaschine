"""
Baut radar.html - die Datenquelle für das "Maschinensuche-Radar"-Artifact - aus den
Treffern der letzten 24 Stunden in treffer.csv. Wird nach jedem Suchlauf aufgerufen
(siehe scheduled-tasks-Prompt "maschinensuche-radar"), damit das Artifact automatisch
aktualisiert werden kann.

Zeigt jede Anzeige nur 24 Stunden lang an (Nutzerwunsch), gruppiert nach Maschinentyp
(gruppe/beschreibung aus config/suchbegriffe.json) und sortiert je Gruppe nach Preis
aufsteigend (Anzeigen ohne erkennbaren Preis stehen am Ende).

Aufruf:
    python scripts/render_radar.py
Gibt am Ende eine kurze Zusammenfassung auf stdout aus (Anzahl sichtbarer Treffer,
Anzahl davon aus diesem letzten Suchlauf), die der aufrufende Agent auswerten kann,
um zu entscheiden, ob eine Push-Benachrichtigung sinnvoll ist.
"""
import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
TREFFER_CSV = PROJEKT_ROOT / "treffer.csv"
CONFIG_SUCHBEGRIFFE = PROJEKT_ROOT / "config" / "suchbegriffe.json"
AUSGABE_HTML = PROJEKT_ROOT / "radar.html"

ANZEIGE_FENSTER = timedelta(hours=24)


def parse_preis_eur(preis: str) -> float | None:
    m = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*(?:€|EUR)\b", preis)
    if not m:
        return None
    try:
        return float(m.group(1).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def lade_suchbegriff_infos() -> dict[str, dict]:
    cfg = json.loads(CONFIG_SUCHBEGRIFFE.read_text(encoding="utf-8"))
    return {
        s["begriff"]: {
            "gruppe": s["gruppe"],
            "beschreibung": s["beschreibung"],
            "hersteller": s.get("hersteller", s["begriff"]),
        }
        for s in cfg["suchbegriffe"]
    }


def lade_sichtbare_zeilen() -> tuple[list[dict], int]:
    with open(TREFFER_CSV, encoding="utf-8-sig", newline="") as f:
        alle = list(csv.DictReader(f))

    grenze = datetime.now(timezone.utc) - ANZEIGE_FENSTER
    sichtbar = []
    letzter_lauf = None
    for z in alle:
        try:
            gefunden_am = datetime.strptime(z["gefunden_am"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        if gefunden_am >= grenze:
            sichtbar.append(z)
            if letzter_lauf is None or gefunden_am > letzter_lauf:
                letzter_lauf = gefunden_am

    aus_letztem_lauf = sum(1 for z in sichtbar if z["gefunden_am"] == max(z["gefunden_am"] for z in sichtbar)) if sichtbar else 0
    return sichtbar, aus_letztem_lauf


def gruppiere(zeilen: list[dict], suchbegriff_infos: dict) -> dict:
    """gruppe -> beschreibung (Maschinentyp) -> hersteller -> Treffer, je Hersteller nach
    Preis aufsteigend sortiert."""
    gruppen = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    fallback = lambda begriff: {"gruppe": "Sonstiges", "beschreibung": begriff, "hersteller": begriff}
    for z in zeilen:
        info = suchbegriff_infos.get(z["suchbegriff"]) or fallback(z["suchbegriff"])
        gruppen[info["gruppe"]][info["beschreibung"]][info["hersteller"]].append(z)

    for beschreibungen in gruppen.values():
        for hersteller_dict in beschreibungen.values():
            for eintraege in hersteller_dict.values():
                eintraege.sort(key=lambda z: (parse_preis_eur(z["preis"]) is None, parse_preis_eur(z["preis"]) or 0))
    return gruppen


GRUPPEN_TAG_KLASSE = {"Landmaschine": "land", "Baumaschine": "bau"}


def render_karte(z: dict) -> str:
    return f"""
    <div class="karte">
      <div class="karte-titel"><a href="{escape(z['url'])}" target="_blank" rel="noopener">{escape(z['titel'])}</a></div>
      <div class="karte-preis">{escape(z['preis'] or '–')}</div>
      <div class="karte-meta">
        <span class="meta-chip">📍 {escape(z['ort'] or 'unbekannt')}</span>
        <span class="meta-chip">{escape(z['portal'])}</span>
        <span class="meta-chip">{escape(z['suchbegriff'])}</span>
      </div>
    </div>"""


def render_gruppe(gruppe_name: str, beschreibungen: dict) -> str:
    tag_klasse = GRUPPEN_TAG_KLASSE.get(gruppe_name, "bau")
    teile_html = []
    for beschreibung, hersteller_dict in sorted(
        beschreibungen.items(), key=lambda kv: -sum(len(v) for v in kv[1].values())
    ):
        gesamt = sum(len(v) for v in hersteller_dict.values())
        hersteller_html = []
        for hersteller, eintraege in sorted(hersteller_dict.items(), key=lambda kv: -len(kv[1])):
            karten = "\n".join(render_karte(z) for z in eintraege)
            hersteller_html.append(f"""
      <div class="hersteller-block">
        <p class="hersteller-titel">{escape(hersteller)} &middot; {len(eintraege)}</p>
        <div class="karten-grid">{karten}</div>
      </div>""")
        teile_html.append(f"""
    <div class="unterkategorie">
      <div class="kategorie-kopf">
        <span class="gruppen-tag {tag_klasse}">{escape(gruppe_name)}</span>
        <h2>{escape(beschreibung)}</h2>
        <span class="kategorie-anzahl">{gesamt} Treffer</span>
      </div>
      {"".join(hersteller_html)}
    </div>""")
    return "\n".join(teile_html)


def render_html(gruppen: dict, gesamt: int, aus_letztem_lauf: int) -> str:
    jetzt = datetime.now(timezone.utc).strftime("%d.%m.%Y, %H:%M UTC")
    if gruppen:
        inhalt = "\n".join(render_gruppe(g, b) for g, b in gruppen.items())
    else:
        inhalt = '<p style="color:var(--text-muted)">Keine Treffer in den letzten 24 Stunden.</p>'

    return f"""<title>Maschinensuche-Radar</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=Public+Sans:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
  :root{{
    --bg: #EAEAE6; --surface: #FFFFFF; --surface-2: #F1F1EB; --text: #201F1B; --text-muted: #605F58;
    --border: #D8D7CC; --accent: #B5650C; --accent-strong: #8F4E08; --accent-soft: #F5E4CE;
    --preis: #2B6E74; --tag-land-bg: #E4EFDD; --tag-land-text: #3E6B2A; --tag-bau-bg: #FCE7D6; --tag-bau-text: #97490F;
    --shadow: 0 1px 2px rgba(32,31,27,0.06), 0 4px 14px rgba(32,31,27,0.05);
  }}
  @media (prefers-color-scheme: dark){{
    :root:not([data-theme="light"]){{
      --bg: #15140F; --surface: #1D1C16; --surface-2: #232219; --text: #EAE8E1; --text-muted: #A19E92;
      --border: #302E24; --accent: #E5A542; --accent-strong: #F0BC6C; --accent-soft: #382A12;
      --preis: #6FC3C9; --tag-land-bg: #253321; --tag-land-text: #92C97F; --tag-bau-bg: #3A2914; --tag-bau-text: #F0A868;
      --shadow: 0 1px 2px rgba(0,0,0,0.35), 0 8px 20px rgba(0,0,0,0.3);
    }}
  }}
  :root[data-theme="dark"]{{
    --bg: #15140F; --surface: #1D1C16; --surface-2: #232219; --text: #EAE8E1; --text-muted: #A19E92;
    --border: #302E24; --accent: #E5A542; --accent-strong: #F0BC6C; --accent-soft: #382A12;
    --preis: #6FC3C9; --tag-land-bg: #253321; --tag-land-text: #92C97F; --tag-bau-bg: #3A2914; --tag-bau-text: #F0A868;
    --shadow: 0 1px 2px rgba(0,0,0,0.35), 0 8px 20px rgba(0,0,0,0.3);
  }}
  *{{ box-sizing: border-box; }}
  body{{ margin: 0; background: var(--bg); color: var(--text); font-family: "Public Sans", -apple-system, "Segoe UI", sans-serif; font-size: 15px; line-height: 1.5; }}
  .wrap{{ max-width: 1000px; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }}
  header{{ display: flex; flex-direction: column; gap: 1.1rem; margin-bottom: 2rem; }}
  .eyebrow{{
    font-family: "IBM Plex Mono", monospace; font-size: 0.72rem; letter-spacing: 0.11em; text-transform: uppercase;
    color: var(--accent-strong); display: flex; align-items: center; gap: 0.5rem;
  }}
  .eyebrow::before{{ content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }}
  h1{{ font-family: "Oswald", "Arial Narrow", sans-serif; font-weight: 600; font-size: clamp(1.9rem, 4vw, 2.6rem); letter-spacing: 0.01em; margin: 0; text-wrap: balance; }}
  .sub{{ color: var(--text-muted); max-width: 68ch; font-size: 0.98rem; }}
  .sub b{{ color: var(--text); font-weight: 600; }}
  .stats{{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.7rem; margin-top: 0.4rem; }}
  .stat{{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 0.85rem 1rem; box-shadow: var(--shadow); }}
  .stat .n{{ font-family: "IBM Plex Mono", monospace; font-weight: 600; font-size: 1.5rem; font-variant-numeric: tabular-nums; display: block; line-height: 1.1; }}
  .stat .n.accent{{ color: var(--accent-strong); }}
  .stat .l{{ font-size: 0.74rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; margin-top: 0.25rem; display: block; }}
  .kategorie-kopf{{ display: flex; align-items: center; flex-wrap: wrap; gap: 0.6rem; margin-bottom: 1rem; }}
  .kategorie-kopf h2{{ font-family: "Oswald", sans-serif; font-weight: 600; font-size: 1.4rem; margin: 0; }}
  .gruppen-tag{{ font-family: "IBM Plex Mono", monospace; font-size: 0.68rem; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; padding: 0.2rem 0.55rem; border-radius: 6px; }}
  .gruppen-tag.bau{{ background: var(--tag-bau-bg); color: var(--tag-bau-text); }}
  .gruppen-tag.land{{ background: var(--tag-land-bg); color: var(--tag-land-text); }}
  .kategorie-anzahl{{ font-family: "IBM Plex Mono", monospace; font-size: 0.85rem; color: var(--text-muted); margin-left: auto; }}
  .unterkategorie{{ margin-bottom: 2rem; }}
  .hersteller-block{{ margin-bottom: 1.1rem; }}
  .hersteller-titel{{
    font-family: "IBM Plex Mono", monospace; font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--text-muted); margin: 0 0 0.5rem 0;
  }}
  .karten-grid{{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 0.7rem; }}
  .karte{{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; box-shadow: var(--shadow); padding: 0.9rem 1rem; display: flex; flex-direction: column; gap: 0.5rem; }}
  .karte-titel a{{ color: var(--text); text-decoration: none; font-weight: 600; font-size: 0.96rem; line-height: 1.3; }}
  .karte-titel a:hover{{ color: var(--accent-strong); text-decoration: underline; }}
  .karte-titel a:focus-visible{{ outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 3px; }}
  .karte-preis{{ font-family: "IBM Plex Mono", monospace; font-variant-numeric: tabular-nums; color: var(--preis); font-weight: 600; font-size: 1.15rem; }}
  .karte-meta{{ display: flex; flex-wrap: wrap; gap: 0.35rem; font-size: 0.78rem; color: var(--text-muted); align-items: center; }}
  .meta-chip{{ display: inline-flex; align-items: center; gap: 0.3rem; font-family: "IBM Plex Mono", monospace; font-size: 0.7rem; background: var(--surface-2); border: 1px solid var(--border); border-radius: 6px; padding: 0.1rem 0.45rem; }}
  footer{{ margin-top: 1.8rem; font-size: 0.82rem; color: var(--text-muted); text-align: center; }}
  footer a{{ color: var(--accent-strong); }}
</style>
<div class="wrap">
  <header>
    <span class="eyebrow">P.Urny Handel &middot; Maschinensuche</span>
    <h1>Maschinensuche-Radar</h1>
    <p class="sub">Zeigt automatisch nur Treffer der letzten <b>24 Stunden</b>, sortiert nach Preis aufsteigend. Preise werden als Nettopreise angenommen, sofern nicht anders angegeben - keine automatische Brutto/Netto-Prüfung. Stand: {jetzt}.</p>
    <div class="stats">
      <div class="stat"><span class="n accent">{gesamt}</span><span class="l">Treffer (24h)</span></div>
      <div class="stat"><span class="n">{aus_letztem_lauf}</span><span class="l">aus letztem Lauf</span></div>
    </div>
  </header>
  {inhalt}
  <footer>Komplette Historie in <a href="https://github.com/Patrick8-75/Suchmaschine/blob/main/treffer.csv" target="_blank" rel="noopener">treffer.csv</a> auf GitHub.</footer>
</div>"""


def main() -> None:
    suchbegriff_infos = lade_suchbegriff_infos()
    sichtbare_zeilen, aus_letztem_lauf = lade_sichtbare_zeilen()
    gruppen = gruppiere(sichtbare_zeilen, suchbegriff_infos)
    html = render_html(gruppen, len(sichtbare_zeilen), aus_letztem_lauf)
    AUSGABE_HTML.write_text(html, encoding="utf-8")
    print(f"radar.html geschrieben: {len(sichtbare_zeilen)} Treffer sichtbar (24h-Fenster), {aus_letztem_lauf} aus dem letzten Lauf.")


if __name__ == "__main__":
    main()
