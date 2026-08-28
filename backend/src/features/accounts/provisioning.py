"""One account, created the same way for the invitation and the access code."""
from src import database
from src.ldap_admin import create_ldap_user


def provision_account(
    *,
    settings,
    uid: str,
    given_name: str,
    surname: str,
    email: str,
    role: str,
    custom_role_id: int | None,
    password: str,
) -> dict:
    """Creates the LDAP person, the whitelist entry and the row in users, returns the session."""
    vorname, nachname = (given_name or "").strip(), (surname or "").strip()
    display_name = " ".join(teil for teil in (vorname, nachname) if teil) or uid

    create_ldap_user(
        settings=settings,
        uid=uid,
        given_name=vorname,
        surname=nachname,
        email=email,
        employee_type="staff" if role == "staff" else "user",
        password=password,
    )

    database.add_to_whitelist(email)
    user_id = database.create_user(
        ldap_username=uid,
        display_name=display_name,
        email=email,
        active=1,
        role=role,
    )
    if role == "custom":
        database.set_user_role(user_id, "custom", custom_role_id)

    return {
        "user_id": user_id,
        "username": uid,
        "display_name": display_name,
        "email": email,
        "role": role,
        "custom_role_id": custom_role_id,
    }
