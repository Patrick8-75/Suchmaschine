# Maschinensuche P.Urny Handel

Durchsucht mehrmals täglich automatisch mehrere Gebrauchtmaschinen-Portale nach Neumeldungen zu
den in `config/suchbegriffe.json` hinterlegten Maschinentypen und trägt neue Treffer in
`treffer.csv` ein.

## Wie du Maschinentypen änderst

Öffne [`config/suchbegriffe.json`](config/suchbegriffe.json) und passe die Liste `suchbegriffe`
an - eine Zeile pro Begriff, z.B. `"Traktor"`, `"Bagger"`, `"Radlader"`. Wörter unter
`ausschluesse.global` werden verwendet, um offensichtliche Fehltreffer (Spielzeug, Ersatzteile
usw.) auszusortieren. Keine Programmierkenntnisse nötig - einfach die Datei bearbeiten und
committen (oder mir im Chat die gewünschte Änderung sagen).

## Portale

Siehe [`config/portale.json`](config/portale.json). Ein Portal lässt sich mit `"aktiv": false`
abschalten, ohne den Eintrag zu löschen.

## Wie die Suche läuft

Eine geplante Cloud-Routine (`claude.ai/code/routines`) klont dieses Repository mehrmals täglich,
liest `config/suchbegriffe.json` und `config/portale.json`, sucht auf jedem aktiven Portal nach
jedem Suchbegriff (Ergebnisse jeweils nach "Neueste" sortiert), vergleicht die gefundenen
Anzeigen-IDs mit `state/gesehene_anzeigen.json` und trägt nur wirklich neue Treffer in
`treffer.csv` ein. Anschließend committet und pusht sie die aktualisierte `state/`- und
`treffer.csv`-Datei in dieses Repo.

**Kein Login/keine Konten:** Es werden ausschließlich öffentlich einsehbare Ergebnislisten
gelesen. Native "Suchauftrag"/Alert-Funktionen einzelner Portale (z.B. Kleinanzeigen,
Technikbörse) werden bewusst NICHT genutzt, da diese ein Benutzerkonto voraussetzen.

## Ergebnisse ansehen

`treffer.csv` in diesem Repo öffnen (z.B. mit Excel) - neueste Einträge stehen unten. Aktuell gibt
es noch **keinen E-Mail-/Chat-Versand** der neuen Treffer, da kein Benachrichtigungskanal
eingerichtet ist (siehe Abschnitt "Offene Punkte").

## Offene Punkte / mögliche Erweiterungen

- **Benachrichtigung:** Aktuell landen neue Treffer nur in `treffer.csv` in diesem Repo. Für eine
  automatische Benachrichtigung (E-Mail, Google Sheet o.ä.) müsste ein passender Connector unter
  claude.ai/customize/connectors verbunden werden - dann kann die Routine entsprechend erweitert
  werden.
- **URL-Muster:** Für eBay Kleinanzeigen und Maschinensucher sind die Such-URLs bereits
  verifiziert (siehe `config/portale.json`). Bei Agriaffaires, Technikbörse, Landwirt.com und
  Mascus ermittelt die Routine die Such-URL bei jedem Lauf selbst über das Suchfeld der jeweiligen
  Startseite - falls ein Portal dabei mal nicht zuverlässig funktioniert, bitte Bescheid geben.
