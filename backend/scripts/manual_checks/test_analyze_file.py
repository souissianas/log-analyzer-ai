#!/usr/bin/env python3
"""
🧪 Test complet de l'endpoint /ollama/analyze-file
Semaine 5: Analyse complète d'un fichier de logs avec Llama 3.2
"""

import httpx
import asyncio
import json
import time
from pathlib import Path


async def test_analyze_file():
    """Teste l'endpoint /ollama/analyze-file avec un vrai fichier log"""
    
    # Chemin du fichier log
    log_file = Path("D:\\downloads\\log-analyzer-ai\\backend\\sample_logs\\application.log")
    
    if not log_file.exists():
        print(f"❌ Fichier non trouvé: {log_file}")
        return
    
    print("=" * 80)
    print("🧠 TEST COMPLET SEMAINE 5 : ANALYSE OLLAMA D'UN FICHIER LOG")
    print("=" * 80)
    
    print(f"\n📁 Fichier à analyser: {log_file.name}")
    print(f"📏 Taille: {log_file.stat().st_size} bytes")
    
    # Lire le fichier
    with open(log_file, "rb") as f:
        content = f.read()
    
    print(f"✓ Fichier chargé en mémoire")
    print(f"\nℹ️  Le fichier contient {len(content.decode('utf-8').splitlines())} lignes")
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            print("\n" + "─" * 80)
            print("📤 Envoi du fichier à l'API FastAPI...")
            print("─" * 80)
            
            # Créer un formulaire multipart
            files = {"file": (log_file.name, content, "text/plain")}
            params = {"max_errors": 5}  # Analyser max 5 erreurs pour gagner du temps
            
            start_time = time.time()
            
            response = await client.post(
                "http://127.0.0.1:8000/ollama/analyze-file",
                files=files,
                params=params,
                timeout=600.0  # 10 minutes pour Llama
            )
            
            elapsed = time.time() - start_time
            
            if response.status_code != 200:
                print(f"\n❌ Erreur HTTP {response.status_code}")
                print(response.text)
                return
            
            data = response.json()
            
            # Afficher les résultats
            print(f"\n✅ RÉPONSE REÇUE (en {elapsed:.1f}s)\n")
            
            print(f"📊 RÉSUMÉ:")
            print(f"  • Fichier: {data['filename']}")
            print(f"  • Erreurs détectées: {data['total_errors_found']}")
            print(f"  • Erreurs analysées: {data['total_analyzed']}")
            print(f"  • Erreurs ignorées: {data['skipped']}")
            
            # Afficher chaque analyse
            for analysis in data.get('analyzed', []):
                print("\n" + "─" * 80)
                print(f"\n🔴 ERREUR #{analysis['index']}")
                print(f"  • Ligne: {analysis['line_number']}")
                print(f"  • Type: {analysis['level']}")
                print(f"  • Timestamp: {analysis['timestamp']}")
                print(f"  • Message: {analysis['message'][:80]}...")
                
                if analysis['success']:
                    print(f"  • Temps d'analyse: {analysis['processing_time_seconds']}s")
                    
                    analysis_data = analysis.get('analysis', {})
                    
                    if analysis_data.get('explanation'):
                        print(f"\n  📌 EXPLICATION:")
                        explanation = analysis_data['explanation']
                        # Afficher au max 200 caractères
                        if len(explanation) > 200:
                            print(f"     {explanation[:200]}...")
                        else:
                            print(f"     {explanation}")
                    
                    if analysis_data.get('causes'):
                        print(f"\n  ⚠️  CAUSES POSSIBLES:")
                        for cause in analysis_data['causes'][:3]:
                            print(f"     • {cause[:100]}")
                    
                    if analysis_data.get('solutions'):
                        print(f"\n  💡 SOLUTIONS:")
                        for solution in analysis_data['solutions'][:3]:
                            print(f"     • {solution[:100]}")
                else:
                    print(f"  ❌ Erreur: {analysis.get('error', 'Erreur inconnue')}")
            
            print("\n" + "=" * 80)
            print("✅ TEST TERMINÉ AVEC SUCCÈS!")
            print("=" * 80)
            
            # Sauvegarder la réponse complète
            output_file = Path("D:\\downloads\\log-analyzer-ai\\backend\\test_results.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 Résultats complets sauvegardés dans: {output_file}")
            
    except asyncio.TimeoutError:
        print("\n❌ TIMEOUT: Llama a pris trop de temps à répondre")
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_analyze_file())
