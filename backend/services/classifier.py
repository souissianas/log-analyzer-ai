ERROR_TAXONOMY: dict[str, list[str]] = {
    # More specific categories first to avoid false matches from generic ones
    "docker": [
        "docker",
        "container",
        "oci runtime",
        "container_linux",
    ],
    "database": [
        "postgres",
        "mysql",
        "sqlite",
        "mongodb",
        "mariadb",
        "psql",
        "pg_",
    ],
    "connection": [
        "timeout",
        "connection refused",
        "econnrefused",
        "failed to connect",
        "connection timed out",
    ],
    "memory": [
        "oom",
        "out of memory",
        "memoryerror",
        "memory usage exceeded",
        "kill process",
    ],
    "disk": [
        "disk full",
        "no space left",
        "no space left on device",
        "structure needs cleaning",
    ],
    "auth": [
        "authentication failed",
        "invalid user",
        "failed password",
        "credentials not found",
    ],
    "ssl": [
        "ssl",
        "certificate",
        "sni does not match",
    ],
    "permission": [
        "permission denied",
        "access denied",
        "exec:",
    ],
}


def classify_error(message: str) -> str:
    normalized = message.lower()
    for category, keywords in ERROR_TAXONOMY.items():
        if any(keyword in normalized for keyword in keywords):
            return category
    return "unknown"
