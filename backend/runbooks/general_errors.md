# Runbook — Erreurs Génériques et Exceptions

## Symptômes courants
- `Internal Server Error` / `500`
- `Exception in thread` / `Traceback`
- `Unexpected error` / `Unhandled exception`
- `NullPointerException` / `AttributeError` / `TypeError`
- `RuntimeError` / `ValueError`

## Diagnostic général

### 1. Trouver le traceback complet
```bash
grep -A 20 "Traceback\|Exception\|ERROR" /var/log/app.log | head -100
# Docker
docker logs log-analyzer-backend --tail=200 2>&1 | grep -A 10 "ERROR\|Exception"
```

### 2. Identifier la fréquence et la tendance
```bash
# Compter les occurrences par heure
grep "ERROR" /var/log/app.log | awk '{print $1, $2}' | cut -d: -f1 | uniq -c
```

### 3. Vérifier les dépendances
```bash
# Python
pip check
# Versions installées
pip list | grep -E "fastapi|pydantic|sqlalchemy"
```

## Bonnes pratiques de débogage

### Activer les logs DEBUG temporairement
```bash
# FastAPI / uvicorn
LOG_LEVEL=debug uvicorn main:app --reload
# Ou via env
export LOG_LEVEL=DEBUG && docker compose up backend
```

### Reproduire en local
```bash
# Utiliser le TestClient FastAPI
from fastapi.testclient import TestClient
client = TestClient(app)
response = client.post("/endpoint", json={...})
print(response.json())
```

## Causes fréquentes
1. **Données inattendues** — input non validé atteignant le code métier
2. **Race condition** — concurrence sur une ressource partagée
3. **Dépendance externe indisponible** — DB, Ollama, API tierce
4. **Configuration manquante** — variable d'env non définie → None
5. **Version de dépendance incompatible** — mise à jour cassante
6. **Ressource épuisée** — pool de connexions, file descriptors

## Solutions recommandées
1. Ajouter des validations Pydantic sur tous les inputs
2. Wrapper les appels externes avec try/except et fallback
3. Implémenter des health checks sur toutes les dépendances
4. Utiliser des timeouts sur tous les appels réseau
5. Activer Sentry ou équivalent pour la capture automatique d'exceptions
6. Mettre en place des tests de régression pour chaque bug corrigé

## Prévention
```python
# Pattern recommandé pour les appels externes
try:
    result = await external_service.call(data)
except ServiceUnavailableError:
    logger.warning("Service indisponible, fallback activé")
    result = fallback_result
except Exception as exc:
    logger.exception("Erreur inattendue", extra={"context": str(data)[:200]})
    raise HTTPException(status_code=500, detail="Erreur interne")
```
