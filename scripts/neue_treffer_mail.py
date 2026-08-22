"""
Wird vom GitHub-Actions-Workflow .github/workflows/email-benachrichtigung.yml aufgerufen.

Ermittelt die Zeilen, die der letzte Push neu an treffer.csv angehängt hat (per git diff
gegen den vorherigen Commit), formatiert sie als lesbaren E-Mail-Text und schreibt:
- email_body.txt          -> E-Mail-Inhalt (leer, wenn keine neuen Treffer)
- $GITHUB_OUTPUT: count=N -> Anzahl neuer Treffer, damit der Workflow den Mail-Versand
                              nur bei N > 0 auslöst
"""
import csv
import os
import subprocess


def get_added_lines():
    try:
        out = subprocess.run(
            ["git", "diff", "--unified=0", "HEAD~1", "HEAD", "--", "treffer.csv"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError:
        # z.B. wenn es noch keinen Vorgänger-Commit gibt
        return []

    lines = []
    for line in out.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            lines.append(line[1:])
    return lines


def main():
    added = get_added_lines()
    rows = list(csv.reader(added))

    entries = []
    for r in rows:
        if len(r) < 8:
            continue
        gefunden_am, portal, suchbegriff, titel, preis, ort, inserat_datum, url = r[:8]
        if gefunden_am == "gefunden_am":
            continue  # Kopfzeile, falls sie erneut im Diff auftaucht
        entries.append(
            f"- [{portal}] {titel}\n"
            f"  Suchbegriff: {suchbegriff} | Preis: {preis} | Ort: {ort} | Datum: {inserat_datum}\n"
            f"  {url}"
        )

    body_path = os.environ.get("BODY_PATH", "email_body.txt")
    with open(body_path, "w", encoding="utf-8") as f:
        if entries:
            f.write(f"{len(entries)} neue Anzeige(n) gefunden:\n\n" + "\n\n".join(entries) + "\n")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"count={len(entries)}\n")


if __name__ == "__main__":
    main()
