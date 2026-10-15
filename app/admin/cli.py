"""Run interactively: python -m app.admin.cli set-password|reset-password."""
import argparse
import getpass
import sqlite3
import sys

from app.admin.security import AdminError, set_password


def main():
    parser = argparse.ArgumentParser(description="Lokaal beheer van het admin-wachtwoord.")
    parser.add_argument("command", choices=["set-password", "reset-password"])
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.exit(1, "Gebruik een interactieve terminal; geef geen wachtwoord als argument.\n")
    password = getpass.getpass("Nieuw admin-wachtwoord: ")
    confirmation = getpass.getpass("Herhaal wachtwoord: ")
    if password != confirmation:
        parser.exit(1, "De wachtwoorden verschillen.\n")
    try:
        set_password(password, reset=args.command == "reset-password")
    except AdminError as exc:
        parser.exit(1, exc.message + "\n")
    except sqlite3.OperationalError:
        parser.exit(1, "Database niet beschikbaar. Controleer het datavolume en migraties.\n")
    print("Wachtwoord opgeslagen. Alle beheersessies zijn beëindigd.")


if __name__ == "__main__":
    main()
