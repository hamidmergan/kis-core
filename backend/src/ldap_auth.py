from ldap3 import Connection, Server, ALL, SUBTREE
from ldap3.core.exceptions import LDAPException

from .config import Settings

settings = Settings()


def authenticate_user(username: str, password: str) -> dict | None:
    if not settings.ldap_server:
        raise RuntimeError("LDAP not configured")

    # Reject an empty password, otherwise it becomes an anonymous bind.
    if not username or not password:
        return None

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

    # Escape the user name, otherwise the filter can be injected.
    from ldap3.utils.conv import escape_filter_chars
    search_filter = f"({settings.ldap_attr_username}={escape_filter_chars(username)})"
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
    # Only an explicit match grants the teacher role.
    if affiliation and affiliation in lecturer_values:
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
