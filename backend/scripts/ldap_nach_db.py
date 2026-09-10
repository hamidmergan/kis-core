"""Moves the directory entries into the database, once before LDAP is switched off.

Usage:
    python scripts/ldap_nach_db.py --ldif dump.ldif
    python scripts/ldap_nach_db.py --server kis-openldap --bind-password ...
"""
import argparse
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import database  # noqa: E402
from src.features.accounts.passwords import (  # noqa: E402
    MAX_PASSWORD_BYTES,
    hash_password,
)

_FELDER = {"uid": "uid", "cn": "cn", "mail": "mail",
           "userpassword": "password", "employeetype": "employee_type"}
_ALLE_FELDER = ("uid", "cn", "mail", "password", "employee_type")


def eintraege_aus_ldif(text: str) -> list[dict]:
    """Reads the people out of a slapcat dump, everything without a uid is skipped."""
    eintraege, aktuell = [], {}
    for zeile in text.splitlines():
        if not zeile.strip():
            if aktuell.get("uid"):
                eintraege.append(_vollstaendig(aktuell))
            aktuell = {}
            continue
        if zeile.startswith(" ") or ":" not in zeile:
            continue
        name, _, wert = zeile.partition(":")
        feld = _FELDER.get(name.strip().lower())
        if feld is None:
            continue
        if wert.startswith(":"):
            # A double colon means the value is base64, slapcat does that for non-ASCII.
            wert = base64.b64decode(wert[1:].strip()).decode("utf-8", "replace")
        aktuell[feld] = wert.strip()
    if aktuell.get("uid"):
        eintraege.append(_vollstaendig(aktuell))
    return eintraege


def _vollstaendig(eintrag: dict) -> dict:
    """Fills the fields the dump left out, so every entry has the same shape."""
    return {feld: eintrag.get(feld, "") for feld in _ALLE_FELDER}


def eintraege_aus_ldap(server: str, port: int, bind_dn: str,
                       bind_password: str, base_dn: str) -> list[dict]:
    """Reads the same fields out of a running directory."""
    from ldap3 import ALL, SUBTREE, Connection, Server

    conn = Connection(Server(server, port=port, get_info=ALL),
                      user=bind_dn, password=bind_password, auto_bind=True)
    conn.search(search_base=base_dn, search_filter="(uid=*)", search_scope=SUBTREE,
                attributes=["uid", "cn", "mail", "userPassword", "employeeType"])
    eintraege = []
    for person in conn.entries:
        roh = person["userPassword"].value if "userPassword" in person else b""
        if isinstance(roh, bytes):
            roh = roh.decode("utf-8", "replace")
        eintraege.append(_vollstaendig({
            "uid": str(person["uid"].value or ""),
            "cn": str(person["cn"].value or ""),
            "mail": str(person["mail"].value or "") if "mail" in person else "",
            "password": roh or "",
            "employee_type": str(person["employeeType"].value or "") if "employeeType" in person else "",
        }))
    conn.unbind()
    return eintraege


def ist_brauchbarer_hash(wert: str | None) -> bool:
    """True for the two shapes the login can check, SSHA and bcrypt."""
    return bool(wert) and (wert.startswith("{SSHA}") or wert.startswith("$2"))


def _hash_fuer(passwort: str) -> str | None:
    """SSHA travels as it is, plain text gets hashed, anything else is refused."""
    if passwort.startswith("{SSHA}"):
        return passwort
    if passwort.startswith("{"):
        # Another scheme like {MD5} would land in the column unusable.
        return None
    if len(passwort.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return None
    return hash_password(passwort)


def uebernehmen(eintraege: list[dict], auch_neue: bool = False) -> dict:
    """Fills in the passwords, a usable hash is never overwritten.

    A directory entry without a row in users means the account was deleted, deleting
    never touched the directory. Such an entry is left alone unless auch_neue is set.
    """
    zahlen = {"angelegt": 0, "ergaenzt": 0, "uebersprungen": 0,
              "abgelehnt": 0, "ohne_zeile": 0}
    for eintrag in eintraege:
        uid = (eintrag.get("uid") or "").strip()
        passwort = (eintrag.get("password") or "").strip()
        if not uid or "@" in uid or not passwort:
            print(f"abgelehnt: uid={uid!r}")
            zahlen["abgelehnt"] += 1
            continue

        hash_wert = _hash_fuer(passwort)
        if hash_wert is None:
            print(f"abgelehnt: uid={uid!r}, Passwort nicht uebernehmbar")
            zahlen["abgelehnt"] += 1
            continue

        vorhanden = database.get_user_by_username(uid)
        if vorhanden is None and not auch_neue:
            print(f"ohne Zeile in users, uebersprungen: uid={uid!r}")
            zahlen["ohne_zeile"] += 1
            continue
        if vorhanden is None:
            mail = (eintrag.get("mail") or "").strip() or None
            if mail:
                database.add_to_whitelist(mail)
            database.create_user(
                ldap_username=uid,
                display_name=(eintrag.get("cn") or "").strip() or uid,
                email=mail,
                active=1,
                role="staff" if eintrag.get("employee_type") == "staff" else "user",
                password_hash=hash_wert,
            )
            zahlen["angelegt"] += 1
        elif not ist_brauchbarer_hash(vorhanden["password_hash"]):
            # An earlier run may have written plain text there, that must not stay.
            database.set_user_password(vorhanden["id"], hash_wert)
            zahlen["ergaenzt"] += 1
        else:
            zahlen["uebersprungen"] += 1
    return zahlen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ldif", type=Path)
    parser.add_argument("--server")
    parser.add_argument("--port", type=int, default=389)
    parser.add_argument("--bind-dn", default="cn=admin,dc=th-luebeck,dc=de")
    parser.add_argument("--bind-password", default="admin")
    parser.add_argument("--base-dn", default="dc=th-luebeck,dc=de")
    parser.add_argument(
        "--auch-neue", action="store_true",
        help="create a row for a directory entry that has none. Off by default, such an "
             "entry usually belongs to an account somebody deleted.",
    )
    args = parser.parse_args()

    if args.ldif:
        eintraege = eintraege_aus_ldif(args.ldif.read_text(encoding="utf-8"))
    elif args.server:
        eintraege = eintraege_aus_ldap(args.server, args.port, args.bind_dn,
                                       args.bind_password, args.base_dn)
    else:
        parser.error("either --ldif or --server is required")

    zahlen = uebernehmen(eintraege, auch_neue=args.auch_neue)
    print(f"\nEintraege gelesen: {len(eintraege)}")
    for name, zahl in zahlen.items():
        print(f"  {name}: {zahl}")

    mit_passwort = _zeilen_mit_passwort()
    print(f"\nZeilen mit Passwort in users: {mit_passwort}")
    erwartet = len(eintraege) - zahlen["abgelehnt"] - zahlen["ohne_zeile"]
    if mit_passwort < erwartet:
        print("ACHTUNG: weniger Zeilen mit Passwort als uebernommene Eintraege")
        return 1
    return 0


def _zeilen_mit_passwort() -> int:
    with database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users WHERE password_hash IS NOT NULL")
            return cur.fetchone()[0]


if __name__ == "__main__":
    raise SystemExit(main())
