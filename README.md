# Maschinensuche P.Urny Handel

Durchsucht mehrere Gebrauchtmaschinen-Portale nach Neumeldungen zu den in
`config/suchbegriffe.json` hinterlegten Maschinentypen. Bei neuen Treffern wird
1. `treffer.csv` ergänzt (komplette Historie, nie gelöscht),
2. das Artifact **[Maschinensuche-Radar](https://claude.ai/code/artifact/ecedfcc4-3818-4dc2-b9f0-fcb53212d639)** aktualisiert (zeigt nur die letzten 24h, Preis aufsteigend sortiert),
3. eine Push-Benachrichtigung an Patrick geschickt.

## Wird manuell gestartet

**Seit dem 04.09.2026 läuft nichts mehr automatisch** (Entscheidung Patrick). Die früheren
zwei Scheduler - eine Windows-Aufgabe und ein geplanter Claude-Task `maschinensuche-radar` -
sind abgeschafft; der letzte automatische Lauf war am 03.09.2026 um 20:22. Lücken in
`treffer.csv` zwischen diesem Datum und dem nächsten Handstart sind also normal und kein
Defekt.

Ablauf eines Laufs:

1. Einmalig, falls noch nicht geschehen: `pip install -r requirements.txt`
2. Suchen und Radar bauen:
   ```
   python scripts/maschinensuche_lokal.py
   python scripts/render_radar.py
   ```
3. Claude sagen: **START** - dann aktualisiert Claude das Radar-Artifact (siehe Hinweis unten)
   und meldet die neuen Treffer. Wer nur "START" schreibt, bekommt auch die Schritte 1-2
   miterledigt.

**Zum Artifact-Update:** Der Publish scheitert beim ersten Versuch regelmäßig mit "You hadn't
viewed the live version of this artifact". Das ist der Normalfall. Lösung: die Artifact-URL
erst mit `action: "read"` lesen (dabei die gespeicherte Datei wirklich vollständig lesen),
danach publizieren. `force: true` nur nach ausdrücklicher Rückfrage.

## Wie du Maschinentypen änderst

Öffne [`config/suchbegriffe.json`](config/suchbegriffe.json) und passe die Liste `suchbegriffe`
an - ein Eintrag pro Begriff mit `begriff` (Suchtext), `gruppe` (`Landmaschine` oder
`Baumaschine` - steuert, welche Portale mitsuchen) und `beschreibung` (Maschinentyp, wird als
Überschrift im Radar verwendet). Wörter unter `ausschluesse.global` sortieren zusätzliche
Fehltreffer aus. Keine Programmierkenntnisse nötig - einfach die Datei bearbeiten und speichern,
der nächste Lauf verwendet dann die neue Liste.

**Ersatzteile/Verschleißteile werden grundsätzlich nicht gemeldet** (Nutzerentscheidung) -
`ist_ersatzteil()` in `scripts/maschinensuche_lokal.py` erkennt gängige Bezeichnungen (Gummikette,
Laufrolle, Hydraulikpumpe, Fahrantrieb, Getriebe, Achse, Dichtung usw.) und filtert sie schon
beim Suchlauf raus, bevor sie in `treffer.csv` landen. Ebenso ausgeschlossen: Spielzeug/Modelle
(`ausschluesse.global`, z.B. "1:32", "Bruder").

**Wichtiger Grundsatz für neue Suchbegriffe (Nutzervorgabe 22.08.2026):** Immer **Hersteller +
Maschinentyp/Modell kombinieren** (z.B. `"Claas Conspeed"`, `"Takeuchi TB 145"`), nie nur die
Marke allein (`"Claas"`) - ein Test hat gezeigt, dass eine reine Markensuche bei einem
verbreiteten Hersteller wie Claas komplett von Traktoren, Spielzeug und Ersatzteilen überflutet
wird und die eigentlich gesuchte Nische (Maispflücker) auf Seite 1 der Ergebnisse gar nicht mehr
auftaucht. Braucht ein Hersteller mehrere Modell-/Produktlinien (z.B. Claas Conspeed UND Corio),
lieber mehrere gezielte Einträge anlegen statt einen breiten.

## Portale - aktueller Stand

Siehe [`config/portale.json`](config/portale.json) für Details je Portal. Dort stehen nur
Portale, die tatsächlich durchsuchbar sind:

| Portal | Status | Gruppe | Grund |
|---|---|---|---|
| eBay Kleinanzeigen | ✅ aktiv | alle | funktioniert zuverlässig |
| Maschinensucher | ✅ aktiv | Baumaschine | funktioniert zuverlässig (eher Baumaschinen-Fokus) |
| Machinerypark | ✅ aktiv | Baumaschine | funktioniert zuverlässig |
| Machineryline | ✅ aktiv | Baumaschine | funktioniert zuverlässig, international |
| Autoline | ⏸️ inaktiv | Baumaschine | technisch OK, aber Duplikate von Machineryline - Nutzerentscheidung, kein technisches Problem |

### Geprüfte, aber nicht nutzbare Portale

Diese Portale wurden getestet und bewusst **komplett aus `config/portale.json` entfernt**
(nicht nur deaktiviert), weil sie sich mit einfachen HTTP-Anfragen nicht durchsuchen lassen.
Falls sich das je ändert (z.B. ein Portal öffnet eine offizielle API, oder wir rüsten auf einen
Headless-Browser um), können sie mit den hier notierten Details wieder in `portale.json`
aufgenommen werden:

| Portal | Grund | Kategorie des Problems |
|---|---|---|
| Agriaffaires (agriaffaires.de) | DataDome-Captcha (geo.captcha-delivery.com) | Bot-Schutz |
| Technikbörse (technikboerse.com) | Explizite Meldung "User-Agent spoofing detected" | Bot-Schutz |
| MachineryZone (machineryzone.de) | DataDome-Captcha (gleiche Unternehmensgruppe wie Agriaffaires) | Bot-Schutz |
| Baupool (baupool.com, nicht .de) | DataDome-Captcha (gleiche Unternehmensgruppe) | Bot-Schutz |
| mobile.de | Blockt Skript-Zugriffe explizit mit "Access denied" (403) | Bot-Schutz |
| Landwirt.com | `/kleinanzeigen?q=` wird serverseitig ignoriert, echte Suche läuft nur per JavaScript | Nur JS-Suche |
| Mascus (mascus.de) | Suchergebnisse werden clientseitig nachgeladen, kein HTML-Inhalt beim Abruf | Nur JS-Suche |
| Die Baumaschinen Börse (die-baumaschinen-boerse.de) | Suche nur über feste Hersteller-Dropdown, Takeuchi nicht gelistet | Keine passende Suche |
| Baggerboerse.de (Zeppelin) | Kein Kauf-Marktplatz, sondern Ankaufs-/Bewertungsformular | Kein Marktplatz |
| AutoScout24 | Reine PKW-Plattform, keine Baumaschinen-Kategorie | Nicht relevant |
| traktorpool.de | DataDome-Captcha (gleiche Unternehmensgruppe wie Agriaffaires/MachineryZone/Baupool) | Bot-Schutz |

Bei "Nur JS-Suche" wäre ein Headless-Browser (z.B. Playwright) die Lösung, siehe
"Mögliche Erweiterungen". Bei "Bot-Schutz" ist automatisiertes Umgehen nicht zulässig - dort
bleibt nur die manuelle Suche im Browser.

## Ergebnisse ansehen

- **Live/aktuell (letzte 24h):** [Maschinensuche-Radar](https://claude.ai/code/artifact/ecedfcc4-3818-4dc2-b9f0-fcb53212d639) - wird bei jedem Handstart aktualisiert, Preis aufsteigend sortiert, ältere Treffer fallen nach 24h raus.
- **Komplette Historie:** `treffer.csv` in diesem Ordner (z.B. mit Excel öffnen) - wird nie gelöscht.
- **Push-Benachrichtigung:** bei neuen Treffern am Ende eines Laufs.

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
