#!/usr/bin/env python3
"""
Test simple upload + save
"""
import httpx
import time

# Créer un fichier de test
with open("test_upload.log", "w") as f:
    f.write("""2026-06-18 10:00:00 INFO Starting
2026-06-18 10:00:01 ERROR Connection failed
2026-06-18 10:00:02 ERROR Retry failed
2026-06-18 10:00:03 CRITICAL Shutting down
""")

print("Uploading file to /analyze endpoint...")
try:
    with open("test_upload.log", "rb") as f:
        files = {"file": (f.name, f)}
        response = httpx.post(
            "http://localhost:8000/analyze",
            files=files,
            timeout=60
        )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Upload réussi")
        print(f"  Filename: {result.get('filename')}")
        print(f"  Entries: {len(result.get('entries', []))}")
        print(f"  Summary: {result.get('summary')}")
    else:
        print(f"✗ Erreur {response.status_code}: {response.text[:200]}")
except Exception as e:
    print(f"✗ Exception: {e}")

# Vérifier la base de données
print("\nVérification de la base de données...")
import sqlite3
import os

db_path = "backend_analysis.db"
if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Vérifier si la table existe
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analyses'")
        if c.fetchone():
            c.execute("SELECT COUNT(*) FROM analyses")
            count = c.fetchone()[0]
            print(f"✓ Table 'analyses' existe avec {count} lignes")
            
            if count > 0:
                c.execute("SELECT id, filename, total_errors_found FROM analyses ORDER BY id DESC LIMIT 3")
                for row in c.fetchall():
                    print(f"  - ID {row[0]}: {row[1]} ({row[2]} erreurs)")
        else:
            print("✗ Table 'analyses' n'existe pas")
        
        conn.close()
    except Exception as e:
        print(f"⚠ Erreur: {e}")
else:
    print("✗ Fichier backend_analysis.db n'existe pas")
