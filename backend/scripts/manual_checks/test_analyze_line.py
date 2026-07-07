#!/usr/bin/env python3
"""Test d'analyse complète d'une ligne de log avec Llama"""

import httpx
import asyncio
import json

async def test_analyze_line():
    """Teste l'endpoint /ollama/analyze-line avec une vraie ligne d'erreur"""
    async with httpx.AsyncClient() as client:
        print("=" * 70)
        print("🧠 TEST D'ANALYSE OLLAMA/LLAMA3.2")
        print("=" * 70)
        
        # Exemple de ligne d'erreur réaliste
        test_log = "2026-06-17 15:45:00 ERROR Database connection timeout: could not connect to server after 30 seconds"
        
        print(f"\n📝 Ligne de log à analyser:")
        print(f"   {test_log}\n")
        
        try:
            print("⏳ Envoi à Llama 3.2... (attendre ~30 secondes)")
            
            r = await client.post(
                'http://127.0.0.1:8000/ollama/analyze-line',
                params={
                    "log_line": test_log,
                    "error_level": "ERROR"
                },
                timeout=180.0  # 3 minutes pour Llama
            )
            
            data = r.json()
            
            if data.get("success"):
                print("\n✅ ANALYSE RÉUSSIE!\n")
                print("=" * 70)
                
                analysis = data.get("analysis", {})
                
                print("\n📌 EXPLICATION:")
                print("-" * 70)
                print(analysis.get("explanation", "N/A"))
                
                print("\n⚠️  CAUSES POSSIBLES:")
                print("-" * 70)
                for i, cause in enumerate(analysis.get("causes", []), 1):
                    print(f"  {i}. {cause}")
                
                print("\n💡 SOLUTIONS RECOMMANDÉES:")
                print("-" * 70)
                for i, solution in enumerate(analysis.get("solutions", []), 1):
                    print(f"  {i}. {solution}")
                
                print("\n" + "=" * 70)
            else:
                print(f"\n❌ ERREUR: {data.get('error', 'Erreur inconnue')}")
                print(f"\nRéponse complète:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                
        except Exception as e:
            print(f"\n❌ Exception: {e}")


if __name__ == "__main__":
    asyncio.run(test_analyze_line())
