import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from core.security import get_current_user_or_api_key
from core.upload import (
    decode_upload,
    read_upload_with_limit,
    validate_log_extension,
)
from schemas.analysis import (
    LegacyAnalyzeResponse,
    LogEntrySchema,
    LogSummarySchema,
)
from services.classifier import classify_error
from services.log_parser import get_log_summary, parse_log_file
from services.ollama_service import explain_logs

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["analyze"],
    dependencies=[Depends(get_current_user_or_api_key)],
    deprecated=True,
)


@router.post(
    "/analyze",
    deprecated=True,
    responses={
        403: {
            "description": (
                "Droit insuffisant pour soumettre une analyse "
                "(rôle admin ou analyst requis)."
            ),
        },
    },
)
async def analyze_log(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[
        dict,
        Depends(get_current_user_or_api_key),
    ],
) -> LegacyAnalyzeResponse:
    """Analyse un fichier de logs avec l'IA."""

    if current_user.get("role") not in ("admin", "analyst"):
        raise HTTPException(
            status_code=403,
            detail="Droit insuffisant pour soumettre une analyse",
        )

    validate_log_extension(file.filename)

    content_bytes = await read_upload_with_limit(file)
    content = decode_upload(content_bytes)

    entries = parse_log_file(content)
    summary = get_log_summary(entries)

    errors = "\n".join(
        entry.message
        for entry in entries
        if entry.level.lower() in {"error", "critical", "fail"}
    )

    ai_explanation = (
        await explain_logs(errors)
        if errors
        else "Aucune erreur détectée"
    )

    return LegacyAnalyzeResponse(
        filename=file.filename,
        summary=LogSummarySchema(**summary),
        ai_explanation=ai_explanation,
        entries=[
            LogEntrySchema(
                line_number=entry.line_number,
                timestamp=entry.timestamp,
                level=entry.level,
                message=entry.message,
                category=classify_error(entry.message),
            )
            for entry in entries
        ],
    )
