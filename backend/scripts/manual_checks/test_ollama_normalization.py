#!/usr/bin/env python3
"""Test unitaire pour la normalisation de la réponse JSON Ollama."""

import unittest
from services.ollama_service import _normalize_analysis


class TestOllamaNormalization(unittest.TestCase):
    def test_normalize_nested_json_string(self):
        raw_response = {
            "explanation": "Le service ne parvient pas à se connecter.",
            "causes": "[\"Problème réseau\", \"Timeout moteur de base\"]",
            "solutions": "[\"Vérifier la connexion\", \"Augmenter le timeout\"]"
        }

        normalized = _normalize_analysis(raw_response)

        self.assertIsInstance(normalized, dict)
        self.assertEqual(normalized["explanation"], "Le service ne parvient pas à se connecter.")
        self.assertEqual(normalized["causes"], ["Problème réseau", "Timeout moteur de base"])
        self.assertEqual(normalized["solutions"], ["Vérifier la connexion", "Augmenter le timeout"])

    def test_normalize_explanation_json_string(self):
        raw_response = {
            "explanation": "{\"explanation\": \"Une erreur de connexion a eu lieu.\", \"causes\": [\"Problème réseau\", \"Timeout\"], \"solutions\": [\"Redémarrer le service\", \"Vérifier le réseau\"]}"
        }

        normalized = _normalize_analysis(raw_response)

        self.assertEqual(normalized["explanation"], "Une erreur de connexion a eu lieu.")
        self.assertEqual(normalized["causes"], ["Problème réseau", "Timeout"])
        self.assertEqual(normalized["solutions"], ["Redémarrer le service", "Vérifier le réseau"])


if __name__ == "__main__":
    unittest.main()
