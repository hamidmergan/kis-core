from ldap3 import Connection, Server, ALL, SUBTREE
from ldap3.core.exceptions import LDAPException

from .config import Settings

settings = Settings()


def authenticate_user(username: str, password: str) -> dict | None:
    if not settings.ldap_server:
        raise RuntimeError("LDAP not configured")

    server = Server(
        settings.ldap_server,
        port=settings.ldap_port,
        use_ssl=settings.ldap_use_ssl,
        get_info=ALL,
    )

    # Step 1: Bind with service account to search
    try:
        service_conn = Connection(
            server,
            user=settings.ldap_bind_dn,
            password=settings.ldap_bind_password,
            auto_bind=True,
        )
    except LDAPException as e:
        raise RuntimeError(f"LDAP service bind failed: {e}") from e

    # Step 2: Search for user by username attribute
    search_filter = f"({settings.ldap_attr_username}={username})"
    service_conn.search(
        search_base=settings.ldap_base_dn,
        search_filter=search_filter,
        search_scope=SUBTREE,
        attributes=[
            settings.ldap_attr_username,
            settings.ldap_attr_fullname,
            settings.ldap_attr_email,
            settings.ldap_attr_affiliation,
        ],
    )

    if not service_conn.entries:
        return None

    user_entry = service_conn.entries[0]
    user_dn = user_entry.entry_dn

    # Step 3: Bind as user to verify password
    try:
        user_conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        user_conn.unbind()
    except LDAPException:
        return None

    # Step 4: Return user attributes
    def attr(name: str) -> str:
        val = user_entry[name].value if name in user_entry else ""
        return (val or "").strip()

    affiliation = attr(settings.ldap_attr_affiliation)
    lecturer_values = [v.strip() for v in settings.ldap_role_lecturer_values.split(",")]
    if not affiliation or affiliation in lecturer_values:
        role = "lecturer"
    else:
        role = "student"

    return {
        "username": attr(settings.ldap_attr_username),
        "fullname": attr(settings.ldap_attr_fullname),
        "email": attr(settings.ldap_attr_email),
        "dn": user_dn,
        "role": role,
    }
