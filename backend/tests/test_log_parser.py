import unittest

from services.log_parser import CRITICAL_LEVELS, get_log_summary, parse_log_file


class TestLogParser(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
