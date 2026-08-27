"""Streams an upload to disk without holding it in memory."""

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
    """Streams the body to disk and returns size and leading bytes."""
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
