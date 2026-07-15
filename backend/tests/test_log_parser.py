import unittest

from services.log_parser import CRITICAL_LEVELS, get_log_summary, parse_log_file


class TestLogParser(unittest.TestCase):
    # ── Tests existants ────────────────────────────────────────────────
    def test_parses_critical_level(self):
        content = "2026-06-18 10:00:00 CRITICAL Service down"
        entries = parse_log_file(content)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, "CRITICAL")
        self.assertEqual(entries[0].message, "Service down")

    def test_parses_all_critical_levels(self):
        content = "\n".join(
            f"2026-06-18 10:00:{i:02d} {level} Sample message"
            for i, level in enumerate(sorted(CRITICAL_LEVELS))
        )

        entries = parse_log_file(content)
        levels = {entry.level for entry in entries}

        self.assertEqual(levels, CRITICAL_LEVELS)

    def test_ignores_info_and_debug(self):
        content = "\n".join(
            [
                "2026-06-18 10:00:00 INFO Application started",
                "2026-06-18 10:00:01 DEBUG Cache warmed",
                "2026-06-18 10:00:02 ERROR Connection refused",
            ]
        )

        entries = parse_log_file(content)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, "ERROR")

    def test_summary_counts_by_level(self):
        content = "\n".join(
            [
                "2026-06-18 10:00:00 ERROR First error",
                "2026-06-18 10:00:01 CRITICAL Second error",
                "2026-06-18 10:00:02 ERROR Third error",
            ]
        )

        entries = parse_log_file(content)
        summary = get_log_summary(entries)

        self.assertEqual(summary["total_critical"], 3)
        self.assertEqual(summary["by_level"]["ERROR"], 2)
        self.assertEqual(summary["by_level"]["CRITICAL"], 1)

    # ── Alias de niveaux ─────────────────────────────────────────────
    def test_warn_alias_maps_to_warning(self):
        """WARN est un alias de WARNING."""
        content = "2026-06-18 10:00:00 WARN Disk usage high"
        entries = parse_log_file(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, "WARNING")

    def test_err_alias_maps_to_error(self):
        """ERR est un alias de ERROR."""
        content = "2026-06-18 10:00:00 ERR Connection dropped"
        entries = parse_log_file(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, "ERROR")

    def test_crit_alias_maps_to_critical(self):
        """CRIT est un alias de CRITICAL."""
        content = "2026-06-18 10:00:00 CRIT Kernel panic"
        entries = parse_log_file(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, "CRITICAL")

    def test_panic_alias_maps_to_fatal(self):
        """PANIC est un alias de FATAL."""
        content = "2026-06-18 10:00:00 PANIC system out of memory"
        entries = parse_log_file(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, "FATAL")

    def test_emerg_alias_maps_to_critical(self):
        """EMERG est un alias de CRITICAL."""
        content = "2026-06-18 10:00:00 EMERG system halted"
        entries = parse_log_file(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, "CRITICAL")

    # ── Format Apache Error Log (pattern 2) ──────────────────────────
    def test_parses_apache_error_log_format(self):
        """Format : [Wed Oct 11 14:32:52 2000] [error] message"""
        content = "[Wed Oct 11 14:32:52 2000] [error] [client 127.0.0.1] mod_rewrite: invalid regex"
        entries = parse_log_file(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, "ERROR")
        self.assertIn("mod_rewrite", entries[0].message)

    def test_parses_apache_critical_log(self):
        content = "[Thu Nov 01 12:00:00.123456 2023] [crit] Server terminated abnormally"
        entries = parse_log_file(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, "CRITICAL")

    # ── Format Syslog RFC3164 (pattern 3) ────────────────────────────
    def test_parses_syslog_format(self):
        """Format : Jun 18 06:30:15 hostname service[pid]: ERROR message"""
        content = "Jun 18 06:30:15 myserver sshd[1234]: ERROR Failed to bind port 22"
        entries = parse_log_file(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, "ERROR")
        self.assertIn("Failed to bind port 22", entries[0].message)

    def test_syslog_info_is_ignored(self):
        content = "Jun 18 06:30:15 myserver sshd[1234]: INFO Connection accepted"
        entries = parse_log_file(content)
        self.assertEqual(len(entries), 0)

    # ── Format fallback level-only (pattern 4) ───────────────────────
    def test_fallback_level_only_error(self):
        """Format : ERROR: message (sans timestamp)"""
        content = "ERROR: connection to database failed"
        entries = parse_log_file(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, "ERROR")

    def test_fallback_bracketed_level(self):
        """Format : [CRITICAL] message"""
        content = "[CRITICAL] disk space exhausted"
        entries = parse_log_file(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, "CRITICAL")

    # ── Format ISO8601 avec timezone (pattern 1 étendu) ────────────────
    def test_parses_iso8601_with_timezone(self):
        content = "2026-06-18T10:05:25.123Z ERROR Service unavailable"
        entries = parse_log_file(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, "ERROR")

    def test_parses_bracketed_timestamp(self):
        content = "[2026-06-18 10:05:25] ERROR: disk quota exceeded"
        entries = parse_log_file(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, "ERROR")

    # ── Cas limites ────────────────────────────────────────────────────
    def test_empty_content_returns_empty_list(self):
        entries = parse_log_file("")
        self.assertEqual(entries, [])

    def test_blank_lines_are_skipped(self):
        content = "\n\n2026-06-18 10:00:00 ERROR Real error\n\n"
        entries = parse_log_file(content)
        self.assertEqual(len(entries), 1)

    def test_line_numbers_are_correct(self):
        content = "\n".join([
            "2026-06-18 10:00:00 INFO ignored",
            "2026-06-18 10:00:01 ERROR line two error",
            "2026-06-18 10:00:02 DEBUG ignored",
            "2026-06-18 10:00:03 CRITICAL line four error",
        ])
        entries = parse_log_file(content)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].line_number, 2)
        self.assertEqual(entries[1].line_number, 4)

    def test_summary_empty_entries(self):
        summary = get_log_summary([])
        self.assertEqual(summary["total_critical"], 0)
        self.assertEqual(summary["by_level"], {})

    def test_timestamp_is_captured(self):
        content = "2026-06-18 10:05:25 ERROR Something failed"
        entries = parse_log_file(content)
        self.assertIn("2026-06-18", entries[0].timestamp)


if __name__ == "__main__":
    unittest.main()
