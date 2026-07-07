from fastapi import HTTPException, UploadFile

from core.config import get_settings


async def read_upload_with_limit(
    file: UploadFile,
    max_size: int | None = None,
) -> bytes:
    limit = max_size or get_settings().max_file_size
    content_bytes = await file.read(limit + 1)
    if len(content_bytes) > limit:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")
    return content_bytes


def decode_upload(content_bytes: bytes) -> str:
    try:
        return content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return content_bytes.decode("latin-1")


def validate_log_extension(filename: str) -> None:
    if not filename.endswith((".log", ".txt", ".out", ".err")):
        raise HTTPException(status_code=400, detail="Format non supporté")
