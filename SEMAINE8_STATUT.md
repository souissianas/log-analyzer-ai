# Semaine 8 - Tests, rapport, soutenance et Docker

## Statut

Prete pour validation finale.

## Objectifs couverts

- Tests unitaires backend.
- Test smoke API complet.
- Build React de production.
- Docker Compose avec PostgreSQL, backend FastAPI et frontend Nginx.
- Documentation de lancement Docker.
- Rapport final.
- Guide de soutenance.

## Fichiers ajoutes ou modifies

- `docker-compose.yml`
- `backend/test_semaine8_smoke.py`
- `RAPPORT_FINAL.md`
- `GUIDE_SOUTENANCE.md`
- `README.md`

## Validation locale sans Docker

Depuis `backend` :

```powershell
python -m unittest test_ollama_normalization test_ollama_nested_explanation test_semaine6_structured_explanations
python -m py_compile services/ollama_service.py test_semaine8_smoke.py
```

Depuis `frontend` :

```powershell
npm run build
```

## Validation fonctionnelle avec backend actif

Ollama doit tourner sur la machine :

```powershell
ollama serve
```

Backend actif sur `http://127.0.0.1:8000`, puis :

```powershell
cd D:\downloads\log-analyzer-ai\backend
python test_semaine8_smoke.py
```

## Lancement Docker

Ollama reste lance sur la machine hote, car il est deja installe localement.

```powershell
cd D:\downloads\log-analyzer-ai
docker compose up --build
```

Services :

- Frontend : `http://localhost:3000`
- Backend : `http://localhost:8000`
- PostgreSQL : `localhost:5432`
- Ollama hote : `http://localhost:11434`

## Criteres de validation finale

- `/health` retourne `{"status":"ok"}`.
- `/ollama/health` indique `ollama_running=true` et `model_available=true`.
- L'interface React accepte un fichier `.log` ou `.txt`.
- Les erreurs detectees sont affichees.
- Les analyses IA contiennent `Explication`, `Causes possibles`, `Solutions recommandees`.
- Une analyse est sauvegardee et visible dans l'historique.
- Le build React passe.
- Docker Compose demarre les services applicatifs.
