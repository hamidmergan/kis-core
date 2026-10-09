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


UTF8_BOM = b"\xef\xbb\xbf"
# Text results a viewer opens on its own after the download, the mark is what tells it UTF-8.
UTF8_TEXT_SUFFIXES = (".md", ".txt")


def utf8_download(text: str | bytes) -> bytes:
    """Text for a download with the UTF-8 mark in front, else Safari opens the saved file as Latin-1 (Ã¼ for ü)."""
    data = text.encode("utf-8") if isinstance(text, str) else text
    return data if data.startswith(UTF8_BOM) else UTF8_BOM + data
