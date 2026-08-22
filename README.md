# Maschinensuche P.Urny Handel

Durchsucht mehrmals täglich automatisch mehrere Gebrauchtmaschinen-Portale nach Neumeldungen zu
den in `config/suchbegriffe.json` hinterlegten Maschinentypen und trägt neue Treffer in
`treffer.csv` ein. Läuft **lokal auf diesem Rechner** über die Windows-Aufgabenplanung (siehe
"Hintergrund" unten für den Grund).

## Einmaliges Setup

1. Python-Pakete installieren:
   ```
   pip install -r requirements.txt
   ```
2. SMTP-Zugangsdaten für die E-Mail-Benachrichtigung hinterlegen (Passwort landet sicher im
   Windows Credential Manager, nicht in einer Datei):
   ```
   python scripts/setup_email_zugangsdaten.py
   ```
3. Testlauf von Hand:
   ```
   python scripts/maschinensuche_lokal.py
   ```
4. Windows-Aufgabenplanung einrichten (läuft danach automatisch, mehrmals täglich):
   ```
   powershell -ExecutionPolicy Bypass -File register_task.ps1
   ```

Der PC muss zu den geplanten Zeiten eingeschaltet/angemeldet sein, damit der Lauf startet.

## Wie du Maschinentypen änderst

Öffne [`config/suchbegriffe.json`](config/suchbegriffe.json) und passe die Liste `suchbegriffe`
an - eine Zeile pro Begriff, aktuell `"Claas Conspeed"` und `"Geringhoff"`. Wörter unter
`ausschluesse.global` sortieren offensichtliche Fehltreffer (Spielzeug, Ersatzteile usw.) aus.
Keine Programmierkenntnisse nötig - einfach die Datei bearbeiten und speichern, der nächste
geplante Lauf verwendet automatisch die neue Liste.

## Portale - aktueller Stand

Siehe [`config/portale.json`](config/portale.json) für Details je Portal. Kurzfassung:

| Portal | Status | Grund |
|---|---|---|
| eBay Kleinanzeigen | ✅ aktiv | funktioniert zuverlässig |
| Maschinensucher | ✅ aktiv | funktioniert zuverlässig (eher Baumaschinen-Fokus) |
| Agriaffaires | ❌ inaktiv | Captcha-/Bot-Schutz (DataDome) - nicht automatisierbar |
| Technikbörse | ❌ inaktiv | aktive Bot-Erkennung blockt Skript-Zugriffe |
| Landwirt.com | ❌ inaktiv | Suche läuft nur per JavaScript, HTTP-Abruf liefert keine echten Treffer |
| Mascus | ❌ inaktiv | Suche läuft nur per JavaScript, HTTP-Abruf liefert keine echten Treffer |

Landwirt.com und Mascus sind keine Bot-Schutz-Fälle, sondern reine JavaScript-Suchen - das lässt
sich mit mehr Aufwand (z.B. per Headless-Browser) nachrüsten, siehe "Mögliche Erweiterungen".

## Ergebnisse ansehen

`treffer.csv` in diesem Ordner öffnen (z.B. mit Excel) - neueste Einträge stehen unten.
Zusätzlich kommt bei jedem Fund automatisch eine E-Mail an **info@urny-handel.com**.

## Hintergrund: warum lokal statt Cloud?

Ursprünglich lief das Ganze als geplante Cloud-Routine. Ein Testlauf hat gezeigt, dass die
Cloud-Umgebung eine Netzwerk-Firewall hat, die den Zugriff auf so gut wie alle normalen Webseiten
blockiert (nur wenige Entwickler-Domains wie github.com sind erlaubt) - alle sechs Portale wurden
mit `EGRESS_BLOCKED` abgewiesen. Das lässt sich nicht umgehen, daher läuft die Suche jetzt lokal
auf diesem Rechner, der normalen Internetzugang hat.

## Mögliche Erweiterungen

- **Landwirt.com / Mascus per Headless-Browser:** Mit z.B. Playwright ließen sich auch diese
  beiden JavaScript-Suchen automatisieren (kein Bot-Schutz, nur clientseitiges Rendering) -
  bei Bedarf einfach Bescheid geben.
- **Weitere Suchbegriffe/Marken** jederzeit in `config/suchbegriffe.json` ergänzbar.
