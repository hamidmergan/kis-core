"""Low-RAM upload streaming, shared by the KI-Tutor and the classic tools.

Both upload paths need the same thing: get a possibly huge request body onto
disk without ever holding it in the backend process. A 500 MB body read with
``await file.read()`` costs 500 MB of RAM per in-flight upload (plus a second
copy when those bytes are handed to storage), which is what tips a small prod
box over.

The head of the body is kept separately so magic-byte / UTF-8 validation still
works without re-reading the file.
"""

from fastapi import HTTPException, UploadFile

from src.i18n import t

UPLOAD_CHUNK = 1024 * 1024   # 1 MiB per stream chunk
HEAD_BYTES = 65536           # kept in RAM for content validation


async def stream_upload_to_path(
    file: UploadFile,
    dest_path: str,
    max_bytes: int,
    locale: str,
) -> tuple[int, bytes]:
    """Stream the request body to ``dest_path`` in chunks.

    Returns ``(total_bytes, head)`` where *head* is the first 64 KiB. Raises
    413 as soon as the body exceeds ``max_bytes``, so an oversize upload is cut
    off mid-stream instead of after it is fully buffered.
    """
    total = 0
    head = bytearray()
    with open(dest_path, "wb") as out:
        while True:
            chunk = await file.read(UPLOAD_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=t("file.tooLargeMb", locale, max=max_bytes // (1024 * 1024)),
                )
            if len(head) < HEAD_BYTES:
                head.extend(chunk[: HEAD_BYTES - len(head)])
            out.write(chunk)
    return total, bytes(head)
