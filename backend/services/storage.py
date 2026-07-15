import os
import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

from core.telemetry import get_tracer
tracer = get_tracer("storage-service")

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

DATABASE_URL = os.environ.get("DATABASE_URL")
SQLITE_DB_PATH = os.environ.get("SQLITE_DB_PATH", "backend_analysis.db")

# Nom d'attribut de span réutilisé à plusieurs endroits (évite la duplication de littéral)
DB_ANALYSIS_ID_ATTR = "db.analysis_id"


def _is_postgres() -> bool:
    return DATABASE_URL is not None and psycopg2 is not None


def _get_sqlite_connection(db_path: str = SQLITE_DB_PATH):
    return sqlite3.connect(db_path)


def _get_postgres_connection(url: str = DATABASE_URL):
    if not psycopg2:
        raise RuntimeError("psycopg2 n'est pas installé. Installez psycopg2-binary pour PostgreSQL.")
    return psycopg2.connect(url)


_postgres_ready = False


def _wait_for_postgres(max_attempts: int = 15, delay_seconds: float = 1.0):
    global _postgres_ready
    if not _is_postgres():
        return
    if _postgres_ready:
        return

    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            conn = _get_postgres_connection()
            conn.close()
            _postgres_ready = True
            return
        except psycopg2.OperationalError as exc:
            last_error = exc
            if attempt == max_attempts:
                raise
            time.sleep(delay_seconds)


def _execute(query: str, params: tuple = (), fetch: bool = False):
    if _is_postgres():
        with _get_postgres_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch:
                    return cur.fetchall()
                return cur.lastrowid
    conn = _get_sqlite_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()] if fetch else None
    rowid = cur.lastrowid
    conn.commit()
    conn.close()
    return rows if fetch else rowid


def check_db_health() -> Dict:
    """Vérifie que la base de données est accessible."""
    backend = "postgresql" if _is_postgres() else "sqlite"
    try:
        if _is_postgres():
            _wait_for_postgres(max_attempts=1, delay_seconds=0.5)
            with _get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
        else:
            conn = _get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            conn.close()
        return {"ok": True, "backend": backend}
    except Exception as exc:
        return {"ok": False, "backend": backend, "error": str(exc)}


def init_db() -> None:
    # NOTE: This function only handles initial table creation (CREATE TABLE IF NOT EXISTS).
    # All schema evolution (ADD/DROP/ALTER COLUMN, indexes, etc.) must go through
    # Alembic migrations in backend/alembic/versions/. Do NOT add ALTER TABLE
    # statements here — use `alembic revision --autogenerate` or create a migration
    # manually and run `alembic upgrade head` to apply it.
    if _is_postgres():
        _wait_for_postgres()
        analyses_query = """
        CREATE TABLE IF NOT EXISTS analyses (
            id SERIAL PRIMARY KEY,
            filename TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            total_errors_found INTEGER NOT NULL DEFAULT 0 CHECK (total_errors_found >= 0),
            total_analyzed INTEGER NOT NULL DEFAULT 0 CHECK (total_analyzed >= 0),
            status VARCHAR(20) DEFAULT 'completed',
            data JSONB DEFAULT '{}'::jsonb
        )
        """
        errors_query = """
        CREATE TABLE IF NOT EXISTS analysis_errors (
            id BIGSERIAL PRIMARY KEY,
            analysis_id BIGINT REFERENCES analyses(id) ON DELETE CASCADE,
            line_number INTEGER,
            level VARCHAR(20),
            message TEXT,
            category VARCHAR(50),
            explanation TEXT,
            causes JSONB DEFAULT '[]'::jsonb,
            solutions JSONB DEFAULT '[]'::jsonb,
            analyzed_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
        otps_query = """
        CREATE TABLE IF NOT EXISTS otps (
            email VARCHAR(255) PRIMARY KEY,
            code VARCHAR(64) NOT NULL,
            expires DOUBLE PRECISION NOT NULL
        )
        """
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_errors_analysis ON analysis_errors(analysis_id)",
        ]
    else:
        analyses_query = """
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            created_at TEXT,
            total_errors_found INTEGER,
            total_analyzed INTEGER,
            status TEXT DEFAULT 'completed',
            data TEXT,
            tenant_id INTEGER,
            user_id INTEGER
        )
        """
        errors_query = """
        CREATE TABLE IF NOT EXISTS analysis_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER REFERENCES analyses(id) ON DELETE CASCADE,
            line_number INTEGER,
            level TEXT,
            message TEXT,
            category TEXT,
            explanation TEXT,
            causes TEXT,
            solutions TEXT,
            analyzed_at TEXT
        )
        """
        otps_query = """
        CREATE TABLE IF NOT EXISTS otps (
            email TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            expires REAL NOT NULL
        )
        """
        tenants_query = """
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            created_at TEXT
        )
        """
        users_query = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'viewer',
            tenant_id INTEGER REFERENCES tenants(id),
            is_active INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT
        )
        """
        # status and created_at are now managed by Alembic migration 003_add_users_status_created_at
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_errors_analysis ON analysis_errors(analysis_id)",
            "CREATE INDEX IF NOT EXISTS idx_analyses_tenant ON analyses(tenant_id)",
        ]

    _execute(analyses_query)
    _execute(errors_query)
    _execute(otps_query)
    if not _is_postgres():
        _execute(tenants_query)
        _execute(users_query)
    # PostgreSQL schema evolution is handled by Alembic (see alembic/versions/)

    for index_query in indexes:
        _execute(index_query)


def _save_analysis_errors(analysis_id: int, analyzed_items: List[Dict], created_at: str) -> None:
    if not analyzed_items:
        return

    if _is_postgres():
        query = """
        INSERT INTO analysis_errors (
            analysis_id, line_number, level, message, category,
            explanation, causes, solutions, analyzed_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        with _get_postgres_connection() as conn:
            with conn.cursor() as cur:
                for item in analyzed_items:
                    analysis = item.get("analysis") or {}
                    cur.execute(
                        query,
                        (
                            analysis_id,
                            item.get("line_number"),
                            item.get("level"),
                            item.get("message"),
                            item.get("category"),
                            analysis.get("explanation"),
                            json.dumps(analysis.get("causes", []), ensure_ascii=False),
                            json.dumps(analysis.get("solutions", []), ensure_ascii=False),
                            created_at,
                        ),
                    )
                conn.commit()
        return

    query = """
    INSERT INTO analysis_errors (
        analysis_id, line_number, level, message, category,
        explanation, causes, solutions, analyzed_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    conn = _get_sqlite_connection()
    cur = conn.cursor()
    for item in analyzed_items:
        analysis = item.get("analysis") or {}
        cur.execute(
            query,
            (
                analysis_id,
                item.get("line_number"),
                item.get("level"),
                item.get("message"),
                item.get("category"),
                analysis.get("explanation"),
                json.dumps(analysis.get("causes", []), ensure_ascii=False),
                json.dumps(analysis.get("solutions", []), ensure_ascii=False),
                created_at,
            ),
        )
    conn.commit()
    conn.close()


def _insert_analysis_postgres(result: Dict, created_at: str, tenant_id: Optional[int], user_id: Optional[int]) -> int:
    query = (
        "INSERT INTO analyses (filename, created_at, total_errors_found, total_analyzed, data, tenant_id, user_id) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id"
    )
    with _get_postgres_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                query,
                (
                    result.get("filename"),
                    created_at,
                    result.get("total_errors_found", 0),
                    result.get("total_analyzed", 0),
                    json.dumps(result, ensure_ascii=False),
                    tenant_id,
                    user_id,
                ),
            )
            row = cur.fetchone()
            analysis_id = row["id"]
            conn.commit()
    return analysis_id


def _insert_analysis_sqlite(result: Dict, created_at: str, tenant_id: Optional[int], user_id: Optional[int]) -> int:
    query = (
        "INSERT INTO analyses (filename, created_at, total_errors_found, total_analyzed, data, tenant_id, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    conn = _get_sqlite_connection()
    cur = conn.cursor()
    cur.execute(
        query,
        (
            result.get("filename"),
            created_at,
            result.get("total_errors_found", 0),
            result.get("total_analyzed", 0),
            json.dumps(result, ensure_ascii=False),
            tenant_id,
            user_id,
        ),
    )
    conn.commit()
    analysis_id = cur.lastrowid
    conn.close()
    return analysis_id


def save_analysis(result: Dict, tenant_id: Optional[int] = None, user_id: Optional[int] = None) -> int:
    """Sauvegarde le dict de résultat et retourne l'id inséré."""
    with tracer.start_as_current_span("save_analysis") as span:
        span.set_attribute("db.filename", result.get("filename", ""))
        span.set_attribute("db.total_errors", result.get("total_errors_found", 0))
        if tenant_id:
            span.set_attribute("db.tenant_id", tenant_id)
        if user_id:
            span.set_attribute("db.user_id", user_id)
        try:
            created_at = datetime.now(timezone.utc).isoformat()
            if _is_postgres():
                analysis_id = _insert_analysis_postgres(result, created_at, tenant_id, user_id)
            else:
                analysis_id = _insert_analysis_sqlite(result, created_at, tenant_id, user_id)

            _save_analysis_errors(analysis_id, result.get("analyzed", []), created_at)
            span.set_attribute(DB_ANALYSIS_ID_ATTR, analysis_id)
            return analysis_id
        except Exception as e:
            span.record_exception(e)
            span.set_status(2, str(e))
            raise


def _get_analysis_postgres(analysis_id: int, tenant_id: Optional[int]) -> Optional[Dict]:
    if tenant_id is not None:
        query = "SELECT id, filename, created_at, total_errors_found, total_analyzed, data FROM analyses WHERE id = %s AND tenant_id = %s"
        params = (analysis_id, tenant_id)
    else:
        query = "SELECT id, filename, created_at, total_errors_found, total_analyzed, data FROM analyses WHERE id = %s"
        params = (analysis_id,)
    with _get_postgres_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            if not row:
                return None
            row["data"] = row["data"] if isinstance(row["data"], dict) else json.loads(row["data"])
            return row


def _get_analysis_sqlite(analysis_id: int, tenant_id: Optional[int]) -> Optional[Dict]:
    conn = _get_sqlite_connection()
    cur = conn.cursor()
    if tenant_id is not None:
        cur.execute(
            "SELECT id, filename, created_at, total_errors_found, total_analyzed, data FROM analyses WHERE id = ? AND tenant_id = ?",
            (analysis_id, tenant_id),
        )
    else:
        cur.execute(
            "SELECT id, filename, created_at, total_errors_found, total_analyzed, data FROM analyses WHERE id = ?",
            (analysis_id,),
        )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None

    # Smell "Extract this nested conditional expression into an independent
    # statement" : la double ternaire imbriquée (dict / JSON valide / vide)
    # est remontée en un if/elif/else lisible avant la construction du dict.
    raw_data = row[5]
    if isinstance(raw_data, dict):
        data = raw_data
    elif raw_data:
        data = json.loads(raw_data)
    else:
        data = None

    return {
        "id": row[0],
        "filename": row[1],
        "created_at": row[2],
        "total_errors_found": row[3],
        "total_analyzed": row[4],
        "data": data,
    }


def get_analysis(analysis_id: int, tenant_id: Optional[int] = None) -> Optional[Dict]:
    with tracer.start_as_current_span("get_analysis") as span:
        span.set_attribute(DB_ANALYSIS_ID_ATTR, analysis_id)
        if tenant_id:
            span.set_attribute("db.tenant_id", tenant_id)
        try:
            if _is_postgres():
                return _get_analysis_postgres(analysis_id, tenant_id)
            return _get_analysis_sqlite(analysis_id, tenant_id)
        except Exception as e:
            span.record_exception(e)
            span.set_status(2, str(e))
            raise


def list_analyses(limit: int = 100, offset: int = 0, tenant_id: Optional[int] = None) -> List[Dict]:
    if _is_postgres():
        if tenant_id is not None:
            query = "SELECT id, filename, created_at, total_errors_found, total_analyzed FROM analyses WHERE tenant_id = %s ORDER BY id DESC LIMIT %s OFFSET %s"
            params = (tenant_id, limit, offset)
        else:
            query = "SELECT id, filename, created_at, total_errors_found, total_analyzed FROM analyses ORDER BY id DESC LIMIT %s OFFSET %s"
            params = (limit, offset)
        with _get_postgres_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                return [dict(row) for row in rows]
    conn = _get_sqlite_connection()
    cur = conn.cursor()
    if tenant_id is not None:
        cur.execute(
            "SELECT id, filename, created_at, total_errors_found, total_analyzed FROM analyses WHERE tenant_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (tenant_id, limit, offset),
        )
    else:
        cur.execute(
            "SELECT id, filename, created_at, total_errors_found, total_analyzed FROM analyses ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
    rows = cur.fetchall()
    conn.close()
    results = []
    for r in rows:
        results.append({
            "id": r[0],
            "filename": r[1],
            "created_at": r[2],
            "total_errors_found": r[3],
            "total_analyzed": r[4],
        })
    return results


def _migrate_analyses_to_postgres(analyses_rows, overwrite: bool) -> Dict:
    """Copie les lignes `analyses` de SQLite vers PostgreSQL en conservant les id.

    Si overwrite est False, une ligne dont l'id existe déjà côté PostgreSQL
    est simplement ignorée. Si overwrite est True, elle est écrasée.
    """
    conflict_clause = (
        "ON CONFLICT (id) DO UPDATE SET "
        "filename = EXCLUDED.filename, "
        "created_at = EXCLUDED.created_at, "
        "total_errors_found = EXCLUDED.total_errors_found, "
        "total_analyzed = EXCLUDED.total_analyzed, "
        "data = EXCLUDED.data"
        if overwrite
        else "ON CONFLICT (id) DO NOTHING"
    )
    query = (
        "INSERT INTO analyses (id, filename, created_at, total_errors_found, total_analyzed, data) "
        "VALUES (%s, %s, %s, %s, %s, %s) " + conflict_clause
    )

    inserted = 0
    skipped = 0
    with _get_postgres_connection() as pg_conn:
        with pg_conn.cursor() as pg_cur:
            for row in analyses_rows:
                pg_cur.execute(
                    query,
                    (
                        row["id"],
                        row["filename"],
                        row["created_at"],
                        row["total_errors_found"],
                        row["total_analyzed"],
                        json.dumps(json.loads(row["data"]) if row["data"] else None, ensure_ascii=False),
                    ),
                )
                if pg_cur.rowcount:
                    inserted += 1
                else:
                    skipped += 1
            # Réaligne la séquence SERIAL sur le plus grand id inséré, pour
            # que les prochains save_analysis() ne re-génèrent pas un id déjà pris.
            pg_cur.execute(
                "SELECT setval(pg_get_serial_sequence('analyses', 'id'), "
                "COALESCE((SELECT MAX(id) FROM analyses), 1))"
            )
            pg_conn.commit()

    return {"inserted": inserted, "skipped": skipped}


def _migrate_errors_to_postgres(error_rows) -> int:
    """Copie les lignes `analysis_errors` de SQLite vers PostgreSQL en conservant les id."""
    if not error_rows:
        return 0

    query = (
        "INSERT INTO analysis_errors "
        "(id, analysis_id, line_number, level, message, category, explanation, causes, solutions, analyzed_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (id) DO NOTHING"
    )
    migrated = 0
    with _get_postgres_connection() as pg_conn:
        with pg_conn.cursor() as pg_cur:
            for row in error_rows:
                pg_cur.execute(
                    query,
                    (
                        row["id"],
                        row["analysis_id"],
                        row["line_number"],
                        row["level"],
                        row["message"],
                        row["category"],
                        row["explanation"],
                        row["causes"],
                        row["solutions"],
                        row["analyzed_at"],
                    ),
                )
                if pg_cur.rowcount:
                    migrated += 1
            pg_cur.execute(
                "SELECT setval(pg_get_serial_sequence('analysis_errors', 'id'), "
                "COALESCE((SELECT MAX(id) FROM analysis_errors), 1))"
            )
            pg_conn.commit()
    return migrated


def migrate_sqlite_to_postgres(overwrite: bool = False) -> Dict:
    """Migre les données SQLite vers PostgreSQL si PostgreSQL est configuré.

    Args:
        overwrite: si True, les lignes déjà présentes côté PostgreSQL (même id)
            sont écrasées par les données SQLite. Si False (par défaut),
            elles sont ignorées et seules les nouvelles lignes sont insérées.
    """
    if not _is_postgres():
        raise RuntimeError("PostgreSQL n'est pas configuré ou psycopg2 n'est pas installé.")

    sqlite_path = SQLITE_DB_PATH
    if not os.path.exists(sqlite_path):
        return {"migrated": 0, "message": "Aucune base SQLite trouvée."}

    # Assure que les tables existent
    init_db()

    conn = _get_sqlite_connection(sqlite_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        "SELECT id, filename, created_at, total_errors_found, total_analyzed, data FROM analyses"
    )
    analyses_rows = cur.fetchall()

    cur.execute(
        "SELECT id, analysis_id, line_number, level, message, category, "
        "explanation, causes, solutions, analyzed_at FROM analysis_errors"
    )
    error_rows = cur.fetchall()
    conn.close()

    analyses_result = _migrate_analyses_to_postgres(analyses_rows, overwrite)
    errors_migrated = _migrate_errors_to_postgres(error_rows)

    return {
        "migrated": analyses_result["inserted"],
        "skipped": analyses_result["skipped"],
        "errors_migrated": errors_migrated,
        "source_rows": len(analyses_rows),
        "overwrite": overwrite,
        "destination": "postgresql",
    }


def get_user_by_email(email: str) -> Optional[Dict]:
    query = "SELECT id, tenant_id, email, role, hashed_password, status FROM users WHERE email = ?"
    if _is_postgres():
        query = query.replace("?", "%s")
    rows = _execute(query, (email,), fetch=True)
    if rows:
        row = dict(rows[0])
        # Backward compat: if no status column, default to 'active'
        if 'status' not in row:
            row['status'] = 'active'
        return row
    return None


def get_user_by_id(user_id: int) -> Optional[Dict]:
    query = "SELECT id, tenant_id, email, role, hashed_password, status FROM users WHERE id = ?"
    if _is_postgres():
        query = query.replace("?", "%s")
    rows = _execute(query, (user_id,), fetch=True)
    if rows:
        row = dict(rows[0])
        if 'status' not in row:
            row['status'] = 'active'
        return row
    return None


def create_user(tenant_id: int, email: str, role: str, hashed_password: str, status: str = 'pending') -> int:
    query = "INSERT INTO users (tenant_id, email, role, hashed_password, status) VALUES (?, ?, ?, ?, ?)"
    if _is_postgres():
        query = "INSERT INTO users (tenant_id, email, role, hashed_password, status) VALUES (%s, %s, %s, %s, %s) RETURNING id"
        with _get_postgres_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (tenant_id, email, role, hashed_password, status))
                row = cur.fetchone()
                conn.commit()
                return row["id"]
    return _execute(query, (tenant_id, email, role, hashed_password, status))


def list_users(tenant_id: Optional[int] = None) -> List[Dict]:
    """Liste tous les utilisateurs, optionnellement filtrés par tenant."""
    if tenant_id is not None:
        query = "SELECT id, tenant_id, email, role, status, created_at FROM users WHERE tenant_id = ? ORDER BY created_at DESC"
        if _is_postgres():
            query = query.replace("?", "%s")
        rows = _execute(query, (tenant_id,), fetch=True)
    else:
        query = "SELECT id, tenant_id, email, role, status, created_at FROM users ORDER BY created_at DESC"
        rows = _execute(query, (), fetch=True)
    return [dict(r) for r in (rows or [])]


def update_user_status(user_id: int, status: str) -> bool:
    """Met à jour le statut d'un utilisateur (pending/active/rejected)."""
    if status not in ('pending', 'active', 'rejected'):
        return False
    query = "UPDATE users SET status = ? WHERE id = ?"
    if _is_postgres():
        query = "UPDATE users SET status = %s WHERE id = %s"
    _execute(query, (status, user_id))
    return True


def update_user_role(user_id: int, role: str) -> bool:
    """Met à jour le rôle d'un utilisateur."""
    if role not in ('admin', 'analyst', 'viewer'):
        return False
    query = "UPDATE users SET role = ? WHERE id = ?"
    if _is_postgres():
        query = "UPDATE users SET role = %s WHERE id = %s"
    _execute(query, (role, user_id))
    return True


def delete_user(user_id: int) -> bool:
    """Supprime un utilisateur."""
    query = "DELETE FROM users WHERE id = ?"
    if _is_postgres():
        query = "DELETE FROM users WHERE id = %s"
    _execute(query, (user_id,))
    return True


def update_user_password(email: str, hashed_password: str) -> bool:
    """Met à jour le mot de passe hashé d'un utilisateur identifié par son email."""
    query = "UPDATE users SET hashed_password = ? WHERE email = ?"
    if _is_postgres():
        query = "UPDATE users SET hashed_password = %s WHERE email = %s"
    _execute(query, (hashed_password, email))
    return True


def count_users_by_tenant(tenant_id: int) -> int:
    """Compte les utilisateurs d'un tenant (pour déterminer le premier admin)."""
    query = "SELECT COUNT(*) as n FROM users WHERE tenant_id = ?"
    if _is_postgres():
        query = query.replace("?", "%s")
    rows = _execute(query, (tenant_id,), fetch=True)
    if rows:
        return int(rows[0].get("n", 0) or 0)
    return 0


def get_tenant_by_slug(slug: str) -> Optional[Dict]:
    if _is_postgres():
        query = "SELECT id, name, slug FROM tenants WHERE slug = %s"
    else:
        query = "SELECT id, name, slug FROM tenants WHERE slug = ?"
    rows = _execute(query, (slug,), fetch=True)
    if rows:
        return dict(rows[0])
    return None


def create_tenant(name: str, slug: str) -> int:
    if _is_postgres():
        query = "INSERT INTO tenants (name, slug) VALUES (%s, %s) RETURNING id"
        with _get_postgres_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (name, slug))
                row = cur.fetchone()
                conn.commit()
                return row["id"]
    query = "INSERT INTO tenants (name, slug) VALUES (?, ?)"
    return _execute(query, (name, slug))


def get_cached_error_analysis(message: str) -> Optional[Dict]:
    """Find a previously saved analysis for the exact same error message."""
    query = "SELECT category, explanation, causes, solutions FROM analysis_errors WHERE message = ? LIMIT 1"
    if _is_postgres():
        query = query.replace("?", "%s")

    try:
        rows = _execute(query, (message,), fetch=True)
        if rows:
            row = dict(rows[0])
            causes = row.get("causes")
            if isinstance(causes, str):
                try:
                    causes = json.loads(causes)
                except Exception:
                    causes = []
            solutions = row.get("solutions")
            if isinstance(solutions, str):
                try:
                    solutions = json.loads(solutions)
                except Exception:
                    solutions = []
            return {
                "category": row.get("category"),
                "analysis": {
                    "explanation": row.get("explanation"),
                    "causes": causes,
                    "solutions": solutions
                }
            }
    except Exception:
        pass
    return None


def _get_dashboard_totals(tenant_filter: str, tenant_params: tuple) -> Dict:
    total_rows = _execute(
        f"SELECT COUNT(*) as n, COALESCE(SUM(total_errors_found),0) as e, COALESCE(SUM(total_analyzed),0) as a FROM analyses{tenant_filter}",
        tenant_params, fetch=True
    )
    totals = dict(total_rows[0]) if total_rows else {}
    return {
        "total_analyses": int(totals.get("n") or 0),
        "total_errors": int(totals.get("e") or 0),
        "total_analyzed": int(totals.get("a") or 0),
    }


def _get_errors_by_level(ph: str, tenant_id: Optional[int], tenant_params: tuple) -> Dict:
    where_clause = f"WHERE a.tenant_id = {ph}" if tenant_id is not None else ""
    level_query = """
        SELECT ae.level, COUNT(*) as cnt
        FROM analysis_errors ae
        JOIN analyses a ON a.id = ae.analysis_id
        {where}
        GROUP BY ae.level
    """.format(where=where_clause)
    level_rows = _execute(level_query, tenant_params, fetch=True)
    return {str(r["level"] or "UNKNOWN").upper(): int(r["cnt"]) for r in (level_rows or [])}


def _get_analyses_per_day(ph: str, tenant_id: Optional[int], tenant_params: tuple) -> List[Dict]:
    if _is_postgres():
        where_clause = f"WHERE tenant_id = {ph}" if tenant_id is not None else "WHERE 1=1"
        day_query = """
            SELECT DATE(created_at::TIMESTAMPTZ) as day, COUNT(*) as cnt, COALESCE(SUM(total_errors_found),0) as errors
            FROM analyses
            {where}
            AND created_at::TIMESTAMPTZ >= NOW() - INTERVAL '7 days'
            GROUP BY DATE(created_at::TIMESTAMPTZ)
            ORDER BY day ASC
        """.format(where=where_clause)
    else:
        where_clause = "WHERE tenant_id = ?" if tenant_id is not None else "WHERE 1=1"
        day_query = """
            SELECT DATE(created_at) as day, COUNT(*) as cnt, COALESCE(SUM(total_errors_found),0) as errors
            FROM analyses
            {where}
            AND created_at >= DATE('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY day ASC
        """.format(where=where_clause)

    day_rows = _execute(day_query, tenant_params, fetch=True)
    return [
        {"day": str(r["day"]), "count": int(r["cnt"]), "errors": int(r["errors"])}
        for r in (day_rows or [])
    ]


def _get_top_files(tenant_filter: str, tenant_params: tuple) -> List[Dict]:
    top_query = f"""
        SELECT filename, COUNT(*) as runs, COALESCE(SUM(total_errors_found),0) as total_errors
        FROM analyses{tenant_filter}
        GROUP BY filename
        ORDER BY runs DESC
        LIMIT 5
    """
    top_rows = _execute(top_query, tenant_params, fetch=True)
    return [
        {"filename": str(r["filename"]), "runs": int(r["runs"]), "total_errors": int(r["total_errors"])}
        for r in (top_rows or [])
    ]


def _get_errors_by_category(ph: str, tenant_id: Optional[int], tenant_params: tuple) -> List[Dict]:
    where_clause = f"WHERE a.tenant_id = {ph}" if tenant_id is not None else ""
    cat_query = """
        SELECT ae.category, COUNT(*) as cnt
        FROM analysis_errors ae
        JOIN analyses a ON a.id = ae.analysis_id
        {where}
        GROUP BY ae.category ORDER BY cnt DESC LIMIT 8
    """.format(where=where_clause)
    cat_rows = _execute(cat_query, tenant_params, fetch=True)
    return [
        {"category": str(r["category"] or "Autre"), "count": int(r["cnt"])}
        for r in (cat_rows or [])
    ]


def get_dashboard_stats(tenant_id: Optional[int] = None) -> Dict:
    """Retourne les statistiques globales pour le dashboard."""
    ph = "%s" if _is_postgres() else "?"
    tenant_filter = f" WHERE tenant_id = {ph}" if tenant_id is not None else ""
    tenant_params = (tenant_id,) if tenant_id is not None else ()

    totals = _get_dashboard_totals(tenant_filter, tenant_params)
    errors_by_level = _get_errors_by_level(ph, tenant_id, tenant_params)
    analyses_per_day = _get_analyses_per_day(ph, tenant_id, tenant_params)
    top_files = _get_top_files(tenant_filter, tenant_params)
    errors_by_category = _get_errors_by_category(ph, tenant_id, tenant_params)

    return {
        "total_analyses": totals["total_analyses"],
        "total_errors": totals["total_errors"],
        "total_analyzed": totals["total_analyzed"],
        "errors_by_level": errors_by_level,
        "analyses_per_day": analyses_per_day,
        "top_files": top_files,
        "errors_by_category": errors_by_category,
    }


def count_analyses(tenant_id: Optional[int] = None) -> int:
    if _is_postgres():
        if tenant_id is not None:
            query = "SELECT COUNT(*) FROM analyses WHERE tenant_id = %s"
            params = (tenant_id,)
        else:
            query = "SELECT COUNT(*) FROM analyses"
            params = ()
        with _get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone()[0]
    conn = _get_sqlite_connection()
    cur = conn.cursor()
    if tenant_id is not None:
        cur.execute("SELECT COUNT(*) FROM analyses WHERE tenant_id = ?", (tenant_id,))
    else:
        cur.execute("SELECT COUNT(*) FROM analyses")
    count = cur.fetchone()[0]
    conn.close()
    return count


def save_otp(email: str, code: str, expires: float) -> None:
    delete_otp(email)
    query = "INSERT INTO otps (email, code, expires) VALUES (%s, %s, %s)" if _is_postgres() else "INSERT INTO otps (email, code, expires) VALUES (?, ?, ?)"
    _execute(query, (email, code, expires))


def get_otp(email: str) -> Optional[dict]:
    query = "SELECT code, expires FROM otps WHERE email = %s" if _is_postgres() else "SELECT code, expires FROM otps WHERE email = ?"
    rows = _execute(query, (email,), fetch=True)
    if rows:
        return {"code": rows[0]["code"], "expires": rows[0]["expires"]}
    return None


def delete_otp(email: str) -> None:
    query = "DELETE FROM otps WHERE email = %s" if _is_postgres() else "DELETE FROM otps WHERE email = ?"
    _execute(query, (email,))
