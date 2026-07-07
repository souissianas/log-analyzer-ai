from prometheus_client import Counter, Histogram, generate_latest

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

OLLAMA_REQUEST_DURATION = Histogram(
    "ollama_request_duration_seconds",
    "Duration of Ollama analysis calls",
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120),
)

LOG_ANALYSIS_TOTAL = Counter(
    "log_analysis_total",
    "Total log file analyses completed",
)

LOG_ERRORS_DETECTED = Counter(
    "log_errors_detected_total",
    "Total log errors detected during parsing",
)


def metrics_payload() -> bytes:
    return generate_latest()
