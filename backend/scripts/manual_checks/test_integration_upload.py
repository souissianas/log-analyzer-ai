#!/usr/bin/env python3
"""
Envoie un fichier de logs de test au backend (/ollama/analyze-file) et affiche la réponse JSON.
"""
import httpx
import json

BACKEND = "http://localhost:8000"
URL = f"{BACKEND}/ollama/analyze-file?output_format=json&max_errors=5"

sample = """2026-06-18 10:00:00 INFO Starting app
2026-06-18 10:00:01 ERROR Connection timeout to database
2026-06-18 10:00:02 ERROR Failed to parse JSON response from API
2026-06-18 10:00:03 CRITICAL Memory usage exceeded 95% threshold
"""

with open("test_integration.log","w",encoding="utf-8") as f:
    f.write(sample)

print(f"Uploading test_integration.log to {URL}\n")

try:
    with open("test_integration.log","rb") as f:
        files = {"file": ("test_integration.log", f, "text/plain")}
        r = httpx.post(URL, files=files, timeout=180.0)

    print("HTTP status:", r.status_code)
    r.raise_for_status()

    try:
        j = r.json()
        print(json.dumps(j, ensure_ascii=False, indent=2))

        assert j.get("filename") == "test_integration.log", "Le nom de fichier est incorrect"
        assert isinstance(j.get("total_errors_found"), int), "total_errors_found doit être un entier"
        assert isinstance(j.get("total_analyzed"), int), "total_analyzed doit être un entier"
        assert isinstance(j.get("analyzed"), list), "analyzed doit être une liste"
        assert len(j["analyzed"]) > 0, "Aucune erreur analysée"

        for item in j["analyzed"]:
            assert isinstance(item.get("analysis"), dict), "analysis doit être un dict"
            assert isinstance(item["analysis"].get("explanation"), str), "analysis.explanation doit être une chaîne"
            assert isinstance(item["analysis"].get("causes"), list), "analysis.causes doit être une liste"
            assert isinstance(item["analysis"].get("solutions"), list), "analysis.solutions doit être une liste"
            assert item["analysis"].get("causes"), "analysis.causes ne doit pas être vide"
            assert item["analysis"].get("solutions"), "analysis.solutions ne doit pas être vide"

        print("\n✅ Structure de l'analyse de fichier validée")
    except AssertionError as assertion_err:
        print("❌ Validation échouée :", assertion_err)
    except Exception:
        print("Response text:\n", r.text)
except Exception as e:
    print("Request failed:", e)
