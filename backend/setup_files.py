main_content = """from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from services.log_parser import parse_log_file, get_log_summary

app = FastAPI(title="Log Analyzer API", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    return {"message": "Log Analyzer API is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/analyze")
async def analyze_log(file: UploadFile = File(...)):
    if not file.filename.endswith((".log", ".txt")):
        raise HTTPException(status_code=400, detail="Format non supporte")
    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content = content_bytes.decode("latin-1")
    entries = parse_log_file(content)
    summary = get_log_summary(entries)
    return {"filename": file.filename, "summary": summary, "entries": [{"line_number": e.line_number, "timestamp": e.timestamp, "level": e.level, "message": e.message} for e in entries]}
"""

parser_content = """import re
from dataclasses import dataclass
from typing import List

@dataclass
class LogEntry:
    line_number: int
    timestamp: str
    level: str
    message: str

CRITICAL_LEVELS = {"ERROR", "WARNING", "FATAL", "EXCEPTION"}

LOG_PATTERN = re.compile(
    r"(\\d{4}-\\d{2}-\\d{2}\\s\\d{2}:\\d{2}:\\d{2})"
    r"\\s+"
    r"(ERROR|WARNING|FATAL|EXCEPTION|INFO|DEBUG)"
    r"\\s+"
    r"(.+)"
)

def parse_log_file(file_content: str) -> List[LogEntry]:
    critical_entries = []
    lines = file_content.splitlines()
    for line_number, line in enumerate(lines, start=1):
        match = LOG_PATTERN.match(line.strip())
        if match:
            timestamp = match.group(1)
            level = match.group(2)
            message = match.group(3)
            if level in CRITICAL_LEVELS:
                critical_entries.append(LogEntry(line_number=line_number, timestamp=timestamp, level=level, message=message))
    return critical_entries

def get_log_summary(entries: List[LogEntry]) -> dict:
    summary = {"total_critical": len(entries), "by_level": {}}
    for entry in entries:
        level = entry.level
        if level not in summary["by_level"]:
            summary["by_level"][level] = 0
        summary["by_level"][level] += 1
    return summary
"""

with open("main.py", "w", encoding="utf-8") as f:
    f.write(main_content)
print("main.py cree !")

with open("services/log_parser.py", "w", encoding="utf-8") as f:
    f.write(parser_content)
print("log_parser.py cree !")