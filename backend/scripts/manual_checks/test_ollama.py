#!/usr/bin/env python3
"""Test script pour vérifier l'intégration Ollama"""

import httpx
import asyncio
import json

async def test_ollama_health():
    """Teste l'endpoint /ollama/health"""
    try:
        async with httpx.AsyncClient() as client:
            print("🔍 Vérification de la santé Ollama...")
            r = await client.get('http://127.0.0.1:8000/ollama/health', timeout=10.0)
            data = r.json()
            print("✅ Réponse reçue:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return data
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return None


async def test_analyze_single_line():
    """Teste l'endpoint /ollama/analyze-line"""
    try:
        async with httpx.AsyncClient() as client:
            print("\n🧠 Test d'analyse d'une ligne de log...")
            
            test_log = "2026-06-17 15:45:00 ERROR Database connection timeout after 30 seconds"
            
            r = await client.post(
                'http://127.0.0.1:8000/ollama/analyze-line',
                params={"log_line": test_log, "error_level": "ERROR"},
                timeout=120.0
            )
            
            data = r.json()
            print("✅ Analyse reçue:")
            print(json.dumps(data, indent=2, ensure_ascii=False))

            assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
            assert data.get("success") is True, f"Analyse échouée: {data.get('error') or data}"

            analysis = data.get("analysis")
            assert isinstance(analysis, dict), "La clé 'analysis' doit être un dict"
            assert isinstance(analysis.get("explanation"), str), "L'explication doit être une chaîne"
            assert isinstance(analysis.get("causes"), list), "Les causes doivent être une liste"
            assert isinstance(analysis.get("solutions"), list), "Les solutions doivent être une liste"
            assert analysis.get("causes"), "La liste des causes ne doit pas être vide"
            assert analysis.get("solutions"), "La liste des solutions ne doit pas être vide"

            print("\n✅ Structure de l'analyse validée")
            return data
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 TEST D'INTÉGRATION OLLAMA + FASTAPI")
    print("=" * 60)
    
    asyncio.run(test_ollama_health())
    asyncio.run(test_analyze_single_line())
    
    print("\n" + "=" * 60)
    print("✓ Tests terminés")
    print("=" * 60)
