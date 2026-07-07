import unittest

from services.classifier import classify_error


class TestClassifier(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()