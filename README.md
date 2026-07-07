# Log Analyzer AI

Application web d'analyse de logs assistée par IA locale (Ollama).  
Upload d'un fichier `.log` / `.txt` → détection des erreurs → explication structurée (explication, causes, solutions) → historique et export PDF.

## Stack

| Couche | Technologie |
|--------|-------------|
| Frontend | React 18, Vite, nginx |
| Backend | FastAPI, Python 3.10+, routers + Pydantic |
| Base de données | SQLite (dev) ou PostgreSQL 15 (Docker) + table `analysis_errors` |
| IA | Ollama + llama3.2 (container Docker inclus) |
| Observabilité | Prometheus `/metrics` (+ Grafana en profile `monitoring`) |

## Démarrage rapide

### Prérequis

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com/) installé localement
- Modèle : `ollama pull llama3.2`

### Développement local

```powershell
# Terminal 1 — Ollama
ollama serve

# Terminal 2 — Backend
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 3 — Frontend
cd frontend
npm install
npm run dev
```

Ouvrir http://localhost:5173

### Docker Compose

```powershell
docker compose up --build
```

- Frontend : http://localhost:3000  
- Backend API : http://localhost:8000  
- Ollama : http://localhost:11434 (service `ollama` + pull auto `llama3.2`)  
- PostgreSQL : port 5432 (dev uniquement)

Observabilité optionnelle :

```powershell
docker compose --profile monitoring up -d
```

- Prometheus : http://localhost:9090  
- Grafana : http://localhost:3001 (admin / admin)

## Fichiers de démonstration

Des logs d'exemple sont disponibles dans `backend/sample_logs/` :

| Fichier | Contexte |
|---------|----------|
| `application.log` | Application Java générique |
| `apache_errors.log` | Erreurs Apache (AH*, SSL, proxy) |
| `docker_container.log` | Erreurs Docker daemon / runtime |
| `jenkins_build.log` | Échecs pipeline CI Jenkins |
| `linux_syslog.log` | Messages système Linux / systemd |

Format attendu : `YYYY-MM-DD HH:MM:SS LEVEL message`

## API principale

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness (application up) |
| `GET /health/ready` | Readiness (DB + Ollama) |
| `GET /metrics` | Métriques Prometheus |
| `POST /ollama/analyze-file` | Pipeline complet upload → IA |
| `GET /logs` | Historique des analyses |
| `POST /logs/{id}/export` | Export PDF |

Limite upload : **10 Mo** par fichier.

### Architecture backend

```
backend/
├── core/          # config, sécurité, upload
├── routers/       # health, analyze, ollama, logs, admin
├── schemas/       # contrats Pydantic
├── services/      # parser, IA, stockage, classifier
└── alembic/       # migrations PostgreSQL
```

### Authentification (API Key)

Si `API_KEY` est défini, les routes protégées exigent le header `X-API-Key`.

```env
API_KEY=change-me-in-production
VITE_API_KEY=change-me-in-production   # frontend Vite
```

Routes publiques : `/`, `/health`, `/health/ready`, `/metrics`.

## Tests

```powershell
cd backend
python -m unittest discover -s tests -p "test_*.py" -v
python -m unittest test_ollama_normalization test_ollama_nested_explanation test_semaine6_structured_explanations -v

cd ../frontend
npm test
```

La CI GitHub Actions exécute tests backend, tests frontend, build Docker et scan Trivy.

## Configuration

Copier `.env.example` vers `.env` et adapter :

```env
DATABASE_URL=postgresql://loganalyzer:changeme123@localhost:5432/loganalyzer
SQLITE_DB_PATH=backend_analysis.db
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
API_KEY=
VITE_API_KEY=
```

Migrations PostgreSQL :

```powershell
cd backend
alembic upgrade head
```

## Documentation

- [Runbook de déploiement](docs/DEPLOYMENT.md)
- Rapports de projet : `RAPPORT_FINAL.md`, `GUIDE_SOUTENANCE.md`

## Licence

Projet académique — usage éducatif.
