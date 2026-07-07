#!/usr/bin/env python3
"""Unit tests for Semaine 6 structured explanations."""

import unittest

from services.ollama_service import (
    _normalize_analysis,
    build_prompt_json,
    parse_ollama_response,
    parse_structured_analysis,
)


class TestSemaine6StructuredExplanations(unittest.TestCase):
    def test_prompt_requests_strict_json_contract(self):
        prompt = build_prompt_json(
            "2026-06-18 10:15:00 ERROR Database timeout after 30s",
            "ERROR",
        )

        self.assertIn('"explanation"', prompt)
        self.assertIn('"causes"', prompt)
        self.assertIn('"solutions"', prompt)
        self.assertIn("objet JSON valide", prompt)
        self.assertIn("Ne mets jamais de JSON imbrique", prompt)

    def test_parse_json_inside_markdown_fence(self):
        raw_response = """```json
{
  "explanation": "La base de donnees ne repond pas dans le delai attendu.",
  "causes": ["Base indisponible", "Timeout trop court"],
  "solutions": ["Verifier le service base de donnees", "Augmenter le timeout"]
}
```"""

        analysis = parse_structured_analysis(raw_response)

        self.assertEqual(
            analysis["explanation"],
            "La base de donnees ne repond pas dans le delai attendu.",
        )
        self.assertEqual(analysis["causes"], ["Base indisponible", "Timeout trop court"])
        self.assertEqual(
            analysis["solutions"],
            ["Verifier le service base de donnees", "Augmenter le timeout"],
        )

    def test_normalize_french_keys_from_model(self):
        raw_response = {
            "explication": "Le service applicatif ne peut pas acceder au cache.",
            "causes_possibles": ["Cache arrete", "Mauvaise URL du cache"],
            "solutions_recommandees": ["Relancer le cache", "Verifier la configuration"],
        }

        analysis = _normalize_analysis(raw_response)

        self.assertEqual(
            analysis["explanation"],
            "Le service applicatif ne peut pas acceder au cache.",
        )
        self.assertEqual(analysis["causes"], ["Cache arrete", "Mauvaise URL du cache"])
        self.assertEqual(analysis["solutions"], ["Relancer le cache", "Verifier la configuration"])

    def test_parse_text_sections_without_numbers(self):
        raw_response = """EXPLICATION
Le serveur a refuse la connexion car le service cible ne semble pas disponible.

CAUSES POSSIBLES
- Service arrete
- Port incorrect

SOLUTIONS RECOMMANDEES
- Redemarrer le service
- Controler la variable d'environnement"""

        analysis = parse_ollama_response(raw_response)

        self.assertIn("refuse la connexion", analysis["explanation"])
        self.assertEqual(analysis["causes"], ["Service arrete", "Port incorrect"])
        self.assertEqual(
            analysis["solutions"],
            ["Redemarrer le service", "Controler la variable d'environnement"],
        )


if __name__ == "__main__":
    unittest.main()
