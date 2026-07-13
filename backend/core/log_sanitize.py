# backend/core/log_sanitize.py
"""
Small helper to prevent log injection (CWE-117).

Any value that comes from the user (filenames, log line content, free-text
query params, etc.) must go through this before being interpolated into a
log message. Without it, an attacker can embed \\n / \\r in their input to
forge fake log lines (e.g. fake "user logged in as admin" entries) or break
log parsers / SIEM ingestion downstream.
"""

_MAX_LOG_VALUE_LEN = 200


def sanitize_for_log(value) -> str:
    """Strips CR/LF and control chars, then truncates. Safe to interpolate into logs."""
    if value is None:
        return ""
    text = str(value)
    # Remove CR/LF (the actual injection vector) and other control chars.
    text = text.replace("\r", " ").replace("\n", " ")
    text = "".join(ch if ch.isprintable() or ch == " " else " " for ch in text)
    if len(text) > _MAX_LOG_VALUE_LEN:
        text = text[:_MAX_LOG_VALUE_LEN] + "...(truncated)"
    return text
