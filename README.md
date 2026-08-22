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

`treffer.csv` in diesem Repo öffnen (z.B. mit Excel) - neueste Einträge stehen unten. Zusätzlich
kommt bei jedem Fund automatisch eine E-Mail (siehe nächster Abschnitt).

## E-Mail-Benachrichtigung einrichten

Sobald die Cloud-Routine neue Treffer in `treffer.csv` pusht, verschickt der GitHub-Actions-
Workflow [`.github/workflows/email-benachrichtigung.yml`](.github/workflows/email-benachrichtigung.yml)
automatisch eine E-Mail an **info@urny-handel.com** mit allen neuen Anzeigen (Titel, Preis, Ort,
Datum, Link). Versendet wird über das Postfach **Microsoft 365 / Outlook** (smtp.office365.com).

**Einmalig einzurichten (nur du, nicht Claude - Zugangsdaten gehören nicht in den Chat):**

1. Auf github.com im Repo [Suchmaschine](https://github.com/Patrick8-75/Suchmaschine) zu
   **Settings → Secrets and variables → Actions → New repository secret**
2. Zwei Secrets anlegen:
   - `SMTP_USERNAME` → deine vollständige Absender-E-Mail-Adresse (z.B. `info@urny-handel.com`)
   - `SMTP_PASSWORD` → das Passwort dieses Postfachs. Falls Multi-Faktor-Authentifizierung aktiv
     ist, brauchst du stattdessen ein **App-Passwort** (in Microsoft 365 unter
     "Sicherheitsinfo" / "App-Passwörter" erstellbar - ggf. muss ein Admin das für den Tenant
     freischalten).
3. Fertig - kein weiterer Schritt nötig. Beim nächsten Fund testet sich der Versand von selbst;
   bei Bedarf lässt sich der Workflow auch manuell unter dem Reiter "Actions" im Repo antriggern
   (Push auf `treffer.csv` simulieren) um es vorher zu prüfen.

Falls der Versand fehlschlägt (z.B. falsches Passwort, Tenant blockiert SMTP-Auth), zeigt der
Actions-Tab im Repo den Fehler im Log an.

## Offene Punkte / mögliche Erweiterungen

- **URL-Muster:** Für eBay Kleinanzeigen und Maschinensucher sind die Such-URLs bereits
  verifiziert (siehe `config/portale.json`). Bei Agriaffaires, Technikbörse, Landwirt.com und
  Mascus ermittelt die Routine die Such-URL bei jedem Lauf selbst über das Suchfeld der jeweiligen
  Startseite - falls ein Portal dabei mal nicht zuverlässig funktioniert, bitte Bescheid geben.
