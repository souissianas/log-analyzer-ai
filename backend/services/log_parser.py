import re
from dataclasses import dataclass
from typing import List

@dataclass
class LogEntry:
    line_number: int
    timestamp: str
    level: str
    message: str

CRITICAL_LEVELS = {
    "ERROR",
    "WARNING",
    "FATAL",
    "EXCEPTION",
    "CRITICAL"
}

LEVEL_MAP = {
    "ERROR": "ERROR", "ERR": "ERROR",
    "WARNING": "WARNING", "WARN": "WARNING",
    "FATAL": "FATAL", "PANIC": "FATAL",
    "EXCEPTION": "EXCEPTION",
    "CRITICAL": "CRITICAL", "CRIT": "CRITICAL", "EMERG": "CRITICAL", "ALERT": "CRITICAL",
    "INFO": "INFO",
    "DEBUG": "DEBUG"
}

LOG_PATTERNS = [
    # 1. Standard / ISO8601 / Docker / RFC5424 / Jenkins ISO timestamp
    # e.g., 2026-06-18 10:05:25 ERROR ...
    # e.g., 2026-06-18T10:05:25.123Z [ERROR] ...
    # e.g., [2026-06-18 10:05:25] ERROR: ...
    re.compile(
        r"^\[?(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\]?"
        r"\s+"
        r"\[?(?P<level>ERROR|WARNING|FATAL|EXCEPTION|CRITICAL|INFO|DEBUG|ERR|WARN|CRIT|EMERG|ALERT|PANIC)\]?:?"
        r"\s+"
        r"(?P<message>.+)$",
        re.IGNORECASE
    ),
    # 2. Apache Error Log
    # e.g., [Wed Oct 11 14:32:52 2000] [error] [client 127.0.0.1] message
    # e.g., [Wed Oct 11 14:32:52.123456 2000] [error] message
    re.compile(
        r"^\[(?P<timestamp>[A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?\s+\d{4})\]"
        r"\s+"
        r"\[(?P<level>ERROR|WARNING|FATAL|EXCEPTION|CRITICAL|INFO|DEBUG|ERR|WARN|CRIT|EMERG|ALERT|PANIC)\]"
        r"\s+"
        r"(?P<message>.+)$",
        re.IGNORECASE
    ),
    # 3. Syslog RFC3164 / BSD syslog (with level)
    # e.g., Jun 18 06:30:15 hostname service[123]: ERROR message
    # e.g., Jun 18 06:30:15 hostname service: [error] message
    re.compile(
        r"^(?P<timestamp>[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"
        r"\s+"
        r"(?:\S+\s+)?"  # hostname
        r"(?:[a-zA-Z0-9_\-\/]+(?:\[\d+\])?:?\s+)?"  # tag/service
        r"\[?(?P<level>ERROR|WARNING|FATAL|EXCEPTION|CRITICAL|INFO|DEBUG|ERR|WARN|CRIT|EMERG|ALERT|PANIC)\]?:?"
        r"\s+"
        r"(?P<message>.+)$",
        re.IGNORECASE
    ),
    # 4. Fallback for logs starting with level directly (sometimes Jenkins logs or simple stdout)
    # e.g., ERROR: message
    # e.g., [CRITICAL] message
    re.compile(
        r"^\[?(?P<level>ERROR|WARNING|FATAL|EXCEPTION|CRITICAL|INFO|DEBUG|ERR|WARN|CRIT|EMERG|ALERT|PANIC)\]?:?"
        r"\s+"
        r"(?P<message>.+)$",
        re.IGNORECASE
    ),
]


def parse_log_file(file_content: str) -> List[LogEntry]:
    critical_entries = []
    lines = file_content.splitlines()
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        for pattern in LOG_PATTERNS:
            match = pattern.match(stripped)
            if match:
                groups = match.groupdict()
                timestamp = groups.get("timestamp", "")
                level_raw = groups.get("level", "")
                message = groups.get("message", "")
                
                level_upper = level_raw.upper()
                level = LEVEL_MAP.get(level_upper, level_upper)
                if level in CRITICAL_LEVELS:
                    critical_entries.append(
                        LogEntry(
                            line_number=line_number,
                            timestamp=timestamp,
                            level=level,
                            message=message
                        )
                    )
                break
    return critical_entries

def get_log_summary(entries: List[LogEntry]) -> dict:
    summary = {"total_critical": len(entries), "by_level": {}}
    for entry in entries:
        level = entry.level
        if level not in summary["by_level"]:
            summary["by_level"][level] = 0
        summary["by_level"][level] += 1
    return summary
