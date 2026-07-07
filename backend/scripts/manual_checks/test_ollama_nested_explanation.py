import unittest
from services.ollama_service import _normalize_analysis


class TestOllamaNestedExplanation(unittest.TestCase):
    def test_explanation_contains_nested_json(self):
        raw_response = {
            "explanation": "{\"explanation\": \"Une erreur est survenue lors du parsing d'une réponse JSON provenant d'une API.\", \"causes\": [\"La réponse de l'API n'est pas dans le format JSON attendu\", \"Le contenu de la réponse n'est pas valide JSON\"], \"solutions\": [\"Vérifier la structure JSON\", \"Valider la réponse avant parsing\"]}",
            "causes": [],
            "solutions": []
        }

        normalized = _normalize_analysis(raw_response)

        self.assertEqual(normalized["explanation"], "Une erreur est survenue lors du parsing d'une réponse JSON provenant d'une API.")
        self.assertEqual(normalized["causes"], ["La réponse de l'API n'est pas dans le format JSON attendu", "Le contenu de la réponse n'est pas valide JSON"])
        self.assertEqual(normalized["solutions"], ["Vérifier la structure JSON", "Valider la réponse avant parsing"])


if __name__ == "__main__":
    unittest.main()
