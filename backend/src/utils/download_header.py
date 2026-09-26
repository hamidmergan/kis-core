"""The download header every route with a file name of its own should send."""

from urllib.parse import quote


def attachment(filename: str) -> str:
    """A download header that is always latin-1 safe and keeps every character of the name.

    A title carries whatever the output language writes. Sent bare, an umlaut reaches the
    browser garbled through the proxy, so the real name travels percent encoded next to an
    ASCII fallback for old clients.
    """
    fallback = filename.encode("ascii", "ignore").decode("ascii").replace('"', "") or "download"
    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{quote(filename)}'
