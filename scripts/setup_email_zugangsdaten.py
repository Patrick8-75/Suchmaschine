"""
Einmaliges Setup: SMTP-Zugangsdaten für den E-Mail-Versand sicher im Windows
Credential Manager hinterlegen (nicht in einer Konfigurationsdatei im Klartext).

Aufruf (im Terminal, NICHT über den Chat - die Eingabe bleibt lokal auf diesem PC):

    python scripts/setup_email_zugangsdaten.py

Fragt interaktiv nach Absender-E-Mail-Adresse und Passwort (Eingabe wird beim
Tippen nicht angezeigt) und speichert beides über das Paket 'keyring' im
Windows Credential Manager. Erneuter Aufruf überschreibt vorhandene Werte.
"""
import getpass

import keyring

KEYRING_SERVICE = "purny-handel-maschinensuche-smtp"


def main() -> None:
    print("SMTP-Zugangsdaten für die Maschinensuche-Benachrichtigung (Microsoft 365 / Outlook).")
    print("Diese Eingabe bleibt lokal auf diesem Rechner (Windows Credential Manager).\n")

    benutzer = input("Absender-E-Mail-Adresse (z.B. info@urny-handel.com): ").strip()
    passwort = getpass.getpass("Passwort / App-Passwort (unsichtbar beim Tippen): ")

    if not benutzer or not passwort:
        print("Abgebrochen - Adresse und Passwort dürfen nicht leer sein.")
        return

    keyring.set_password(KEYRING_SERVICE, "smtp_username", benutzer)
    keyring.set_password(KEYRING_SERVICE, "smtp_password", passwort)
    print(f"\nGespeichert für {benutzer}. Ab jetzt verschickt maschinensuche_lokal.py automatisch E-Mails.")


if __name__ == "__main__":
    main()
