import unittest

from services.classifier import classify_error


class TestClassifier(unittest.TestCase):
    # ── Catégories existantes ──────────────────────────────────────────────
    def test_classifies_connection_errors(self):
        self.assertEqual(
            classify_error("ERROR Connection timeout to database after 30s"),
            "connection",
        )

    def test_classifies_memory_errors(self):
        self.assertEqual(
            classify_error("CRITICAL Out of memory: Kill process 4512 (java)"),
            "memory",
        )

    def test_classifies_disk_errors(self):
        self.assertEqual(
            classify_error("ERROR no space left on device"),
            "disk",
        )

    def test_returns_unknown_for_generic_messages(self):
        self.assertEqual(classify_error("ERROR Something unexpected happened"), "unknown")

    # ── Nouvelles catégories ───────────────────────────────────────────────
    def test_classifies_docker_errors(self):
        self.assertEqual(classify_error("CRITICAL docker daemon not responding"), "docker")

    def test_classifies_container_errors(self):
        self.assertEqual(classify_error("ERROR container exited with code 1"), "docker")

    def test_classifies_oci_runtime_errors(self):
        self.assertEqual(classify_error("ERROR oci runtime exec failed"), "docker")

    def test_classifies_database_postgres(self):
        self.assertEqual(classify_error("ERROR postgres connection pool exhausted"), "database")

    def test_classifies_database_mysql(self):
        self.assertEqual(classify_error("ERROR mysql server has gone away"), "database")

    def test_classifies_database_sqlite(self):
        self.assertEqual(classify_error("ERROR sqlite3.OperationalError: disk I/O error"), "database")

    def test_classifies_database_pg_prefix(self):
        self.assertEqual(classify_error("ERROR pg_query failed: relation does not exist"), "database")

    def test_classifies_auth_failed_password(self):
        self.assertEqual(classify_error("WARNING failed password for admin from 192.168.1.1"), "auth")

    def test_classifies_auth_invalid_user(self):
        self.assertEqual(classify_error("ERROR invalid user root from 10.0.0.1"), "auth")

    def test_classifies_auth_authentication_failed(self):
        self.assertEqual(classify_error("ERROR authentication failed for user testuser"), "auth")

    def test_classifies_ssl_certificate(self):
        self.assertEqual(classify_error("ERROR certificate verify failed: unable to get local issuer"), "ssl")

    def test_classifies_ssl_keyword(self):
        self.assertEqual(classify_error("ERROR ssl handshake failed"), "ssl")

    def test_classifies_permission_denied(self):
        self.assertEqual(classify_error("ERROR permission denied: /etc/shadow"), "permission")

    def test_classifies_access_denied(self):
        self.assertEqual(classify_error("ERROR access denied for user 'root'@'localhost'"), "permission")

    def test_classifies_connection_refused(self):
        self.assertEqual(classify_error("ERROR ECONNREFUSED 127.0.0.1:5432"), "connection")

    def test_classifies_failed_to_connect(self):
        self.assertEqual(classify_error("ERROR failed to connect to Redis"), "connection")

    def test_classifies_oom_keyword(self):
        self.assertEqual(classify_error("CRITICAL OOM killer invoked"), "memory")

    def test_classifies_memory_error_keyword(self):
        self.assertEqual(classify_error("CRITICAL MemoryError: cannot allocate"), "memory")

    def test_classifies_disk_full(self):
        self.assertEqual(classify_error("ERROR disk full on /dev/sda1"), "disk")

    def test_classifies_structure_needs_cleaning(self):
        self.assertEqual(classify_error("ERROR structure needs cleaning"), "disk")

    # ── Cas limites ────────────────────────────────────────────────────────
    def test_case_insensitive(self):
        """Le classifier est insensible à la casse."""
        self.assertEqual(classify_error("ERROR PERMISSION DENIED /var/log"), "permission")

    def test_empty_string_returns_unknown(self):
        self.assertEqual(classify_error(""), "unknown")

    def test_first_matching_category_wins(self):
        """'docker' est avant 'connection' dans ERROR_TAXONOMY, donc docker doit gagner."""
        result = classify_error("docker container connection timeout")
        self.assertEqual(result, "docker")


if __name__ == "__main__":
    unittest.main()