import unittest
from unittest.mock import MagicMock

from pypdf import PdfReader

from services.pdf_export import build_analysis_pdf, safe_str


def _extract_text(bio) -> str:
    """Helper: extracts all text from a generated PDF BytesIO for content assertions."""
    bio.seek(0)
    reader = PdfReader(bio)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


class TestPDFExport(unittest.TestCase):
    def test_safe_str_removes_unsupported_chars(self):
        # Unicode quote, em-dash, and emojis should be cleaned up
        input_str = "L’erreur — critique 🚨"
        output_str = safe_str(input_str)
        
        self.assertNotIn("’", output_str)
        self.assertNotIn("—", output_str)
        self.assertNotIn("🚨", output_str)
        self.assertIn("'", output_str)
        self.assertIn("-", output_str)
        self.assertIn("[ALERT]", output_str)

    def test_safe_str_handles_non_string(self):
        self.assertEqual(safe_str(None), "")
        self.assertEqual(safe_str(123), "123")

    def test_build_analysis_pdf_handles_none_analysis(self):
        # Simulate log item where "analysis" is None or missing
        mock_item = {
            "id": 1,
            "created_at": "2026-06-22T12:00:00Z",
            "data": {
                "filename": "test.log",
                "analyzed": [
                    {
                        "index": 1,
                        "level": "ERROR",
                        "message": "Something went wrong — standard error",
                        "category": "database",
                        "analysis": None  # Trigger potential NoneType bug
                    }
                ]
            }
        }
        
        bio = build_analysis_pdf(mock_item)
        self.assertIsNotNone(bio)
        pdf_data = bio.getvalue()
        self.assertGreater(len(pdf_data), 0)

    def test_build_analysis_pdf_handles_accented_chars(self):
        mock_item = {
            "id": 2,
            "created_at": "2026-06-22T12:00:00Z",
            "data": {
                "filename": "test.log",
                "analyzed": [
                    {
                        "index": 1,
                        "level": "ERROR",
                        "message": "Erreur d'accès à la base de données",
                        "category": "database",
                        "analysis": {
                            "explanation": "Une erreur est survenue lors de l'exécution d'une requête.",
                            "causes": ["Problème réseau", "Temps d'attente dépassé"],
                            "solutions": ["Vérifier le réseau", "Augmenter le timeout"]
                        }
                    }
                ]
            }
        }
        
        bio = build_analysis_pdf(mock_item)
        self.assertIsNotNone(bio)
        pdf_data = bio.getvalue()
        self.assertGreater(len(pdf_data), 0)

    def test_build_analysis_pdf_content_matches_input(self):
        """Vérifie que le texte réellement présent dans le PDF correspond aux
        données fournies, et pas seulement que le fichier a été généré."""
        mock_item = {
            "id": 42,
            "created_at": "2026-06-22T12:00:00Z",
            "data": {
                "filename": "app-prod.log",
                "analyzed": [
                    {
                        "index": 1,
                        "level": "CRITICAL",
                        "category": "database",
                        "message": "Connection pool exhausted",
                        "analysis": {
                            "explanation": "Le pool de connexions est sature.",
                            "causes": ["Trop de connexions ouvertes", "Fuite de connexion"],
                            "solutions": ["Augmenter la taille du pool", "Fermer les connexions inutilisees"],
                        },
                    }
                ],
            },
        }

        bio = build_analysis_pdf(mock_item)
        text = _extract_text(bio)

        # Header content
        self.assertIn("app-prod.log", text)
        self.assertIn("42", text)

        # Error item content
        self.assertIn("CRITICAL", text)
        self.assertIn("database", text)
        self.assertIn("Connection pool exhausted", text)

        # Analysis content: explanation, causes, and solutions must all be
        # findable in the rendered PDF, not just present in the input dict.
        self.assertIn("Le pool de connexions est sature", text)
        self.assertIn("Trop de connexions ouvertes", text)
        self.assertIn("Fuite de connexion", text)
        self.assertIn("Augmenter la taille du pool", text)
        self.assertIn("Fermer les connexions inutilisees", text)

    def test_build_analysis_pdf_multiple_items_all_present(self):
        """Avec plusieurs erreurs, chaque message doit apparaitre dans le PDF
        (regression pour un bug ou seule la derniere erreur etait rendue)."""
        mock_item = {
            "id": 7,
            "created_at": "2026-06-22T12:00:00Z",
            "data": {
                "filename": "multi.log",
                "analyzed": [
                    {"index": 1, "level": "ERROR", "category": "network",
                     "message": "Timeout upstream", "analysis": None},
                    {"index": 2, "level": "WARNING", "category": "auth",
                     "message": "Token bientot expire", "analysis": None},
                ],
            },
        }

        bio = build_analysis_pdf(mock_item)
        text = _extract_text(bio)

        self.assertIn("Timeout upstream", text)
        self.assertIn("Token bientot expire", text)
        self.assertIn("network", text)
        self.assertIn("auth", text)


if __name__ == "__main__":
    unittest.main()