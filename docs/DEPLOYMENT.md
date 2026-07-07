# Runbook de déploiement — Log Analyzer AI v2.1

Guide opérationnel complet pour lancer, configurer et dépanner l'application,
incluant toutes les fonctionnalités P3 : RAG, Celery, RBAC/JWT, Loki, Jaeger, Helm/K8s.

---

## Table des matières

1. [Variables d'environnement](#1-variables-denvironnement)
2. [Docker Compose — démarrage rapide](#2-docker-compose--démarrage-rapide)
3. [Profil Monitoring (Loki + Grafana + Jaeger)](#3-profil-monitoring)
4. [RAG — Ingestion des runbooks](#4-rag--ingestion-des-runbooks)
5. [Authentification JWT + RBAC](#5-authentification-jwt--rbac)
6. [Analyse asynchrone (Celery + SSE)](#6-analyse-asynchrone-celery--sse)
7. [OpenTelemetry Tracing](#7-opentelemetry-tracing)
8. [Développement local](#8-développement-local)
9. [Migrations Alembic](#9-migrations-alembic)
10. [Kubernetes / Helm](#10-kubernetes--helm)
11. [CI/CD — GitHub Actions + Jenkins](#11-cicd--github-actions--jenkins)
12. [SonarQube — qualité code](#12-sonarqube--qualité-code)
13. [Dépannage](#13-dépannage)
14. [Checklist soutenance](#14-checklist-soutenance)

---

## 1. Variables d'environnement

Copier `.env.example` en `.env` et ajuster les valeurs :

```bash
cp .env.example .env
```

| Variable | Défaut | Description |
|---|---|---|
| `POSTGRES_PASSWORD` | `changeme123` | Mot de passe PostgreSQL |
| `API_KEY` | *(vide = désactivé)* | Clé API legacy (header `X-API-Key`) |
| `JWT_SECRET_KEY` | `change-me-in-production` | Secret JWT — **à changer impérativement en prod** |
| `OLLAMA_MODEL` | `llama3.2` | Modèle Ollama à utiliser |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Origines CORS autorisées |
| `OTLP_ENDPOINT` | *(vide)* | URL Jaeger OTLP gRPC, ex. `http://jaeger:4317` |
| `REDIS_URL` | `redis://redis:6379/0` | URL broker Redis pour Celery |
| `CHROMADB_HOST` | `chromadb` | Hôte ChromaDB pour le RAG |
| `GRAFANA_PASSWORD` | `admin` | Mot de passe Grafana |

> [!CAUTION]
> Ne jamais committer le fichier `.env`. Il est déjà dans `.gitignore`.

---

## 2. Docker Compose — démarrage rapide

### Stack complète (recommandé)

```bash
docker compose up --build -d
docker compose ps
```

Services et ports :

| Service | Port | Rôle |
|---|---|---|
| `frontend` | 3000 | Interface React |
| `backend` | 8000 | API FastAPI |
| `postgres` | 5432 | Base de données |
| `redis` | 6379 | Broker Celery |
| `chromadb` | 8080 | Vecteurs RAG |
| `ollama` | 11434 | LLM local |
| `celery-worker` | — | Worker d'analyse async |

Le service `ollama-init` télécharge automatiquement `llama3.2` et `nomic-embed-text`.

### Vérifications après démarrage

```bash
# Backend sain
curl http://localhost:8000/health/ready

# Réponse attendue
# { "status": "ready", "database": { "ok": true }, "ollama": { "ollama_running": true } }

# Frontend
curl -I http://localhost:3000/
```

---

## 3. Profil Monitoring

Active Prometheus, Grafana, Loki, Promtail et Jaeger :

```bash
docker compose --profile monitoring up -d
```

| Interface | URL | Identifiants |
|---|---|---|
| Grafana | http://localhost:3001 | `admin` / `admin` |
| Prometheus | http://localhost:9090 | — |
| Jaeger UI | http://localhost:16686 | — |
| Loki | http://localhost:3100 | — |

### Dashboards Grafana pré-provisionnés

- **Log Analyzer — Backend API** : RPS, taux d'erreur, latence p95
- **Log Analyzer — Ollama AI Engine** : durée d'analyse, timeouts, RAG

### Logs dans Loki

Dans Grafana → Explore → datasource **Loki** :

```logql
{container="log-analyzer-backend"} | json
```

---

## 4. RAG — Ingestion des runbooks

Le RAG enrichit les prompts Ollama avec des runbooks opérationnels internes.

### Ingestion initiale (une seule fois)

```bash
# Attendre que ChromaDB et Ollama soient healthy
docker compose exec backend python scripts/ingest_runbooks.py
```

Runbooks inclus :
- `connection_errors.md` — timeout, connexion refusée
- `memory_errors.md` — OOM, MemoryError
- `disk_errors.md` — No space left
- `auth_errors.md` — authentification, credentials
- `ssl_errors.md` — certificats, TLS
- `general_errors.md` — exceptions génériques

### Désactiver le RAG

Le RAG se désactive automatiquement si ChromaDB est inaccessible. Pas de configuration nécessaire.

### Ajouter un runbook personnalisé

1. Créer un fichier `.md` dans `backend/runbooks/`
2. Relancer le script d'ingestion :

```bash
docker compose exec backend python scripts/ingest_runbooks.py
```

---

## 5. Authentification JWT + RBAC

### Inscription (première utilisation)

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "motdepasse123",
    "tenant_name": "Mon Entreprise",
    "tenant_slug": "mon-entreprise",
    "role": "admin"
  }'
```

### Connexion

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "motdepasse123"}'
```

Réponse : `{"access_token": "eyJ...", "role": "admin", "email": "admin@example.com"}`

### Utiliser le token

```bash
export TOKEN="eyJ..."
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/logs
```

### Rôles et permissions

| Rôle | Consulter | Analyser | Exporter PDF | Ré-analyser | Supprimer |
|---|:---:|:---:|:---:|:---:|:---:|
| `viewer` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `analyst` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `admin` | ✅ | ✅ | ✅ | ✅ | ✅ |

> [!IMPORTANT]
> Changer `JWT_SECRET_KEY` en production. La valeur par défaut est publique.

### Isolation multi-tenant

Chaque utilisateur appartient à un **tenant** (organisation). Les analyses sont filtrées par `tenant_id` — un utilisateur ne peut pas voir les analyses d'un autre tenant.

---

## 6. Analyse asynchrone (Celery + SSE)

### Workflow

1. **Soumission** : `POST /jobs/analyze` → retourne `{"job_id": "uuid"}`
2. **Progression** : `GET /jobs/{job_id}/stream` → SSE avec `{current, total, status}`
3. **Résultat** : `GET /jobs/{job_id}/result` → analyse complète

```bash
# Soumettre un job
curl -X POST http://localhost:8000/jobs/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@backend/sample_logs/docker_container.log" \
  -F "max_errors=5"

# Sonder l'état
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/jobs/{job_id}/status
```

### Supervision du worker Celery

```bash
# Logs du worker
docker compose logs celery-worker --tail 50 -f

# Statut des tâches
docker compose exec celery-worker celery -A worker inspect active
```

---

## 7. OpenTelemetry Tracing

Activé automatiquement si `OTLP_ENDPOINT` est défini.

```bash
# Avec le profil monitoring (Jaeger inclus)
OTLP_ENDPOINT=http://jaeger:4317 docker compose --profile monitoring up -d
```

Spans instrumentés :
- Toutes les requêtes HTTP FastAPI (auto)
- `analyze_with_ollama` — avec attributs `log.level`, `ollama.model`, `rag.used`
- `check_ollama_health`
- `save_analysis` / `get_analysis` — avec `db.filename`, `db.analysis_id`

Visualisation dans **Jaeger UI** (http://localhost:16686) → service `log-analyzer-backend`.

---

## 8. Développement local

```powershell
# 1. Ollama
ollama serve
ollama pull llama3.2
ollama pull nomic-embed-text   # pour le RAG

# 2. Redis (optionnel — pour Celery async)
docker run -p 6379:6379 redis:7-alpine

# 3. ChromaDB (optionnel — pour le RAG)
docker run -p 8080:8080 chromadb/chroma:0.5.5

# 4. Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 5. Frontend
cd frontend
npm install
npm run dev
```

### Lancer le worker Celery en local

```bash
cd backend
celery -A worker worker --loglevel=info --concurrency=2 -Q analysis
```

---

## 9. Migrations Alembic

```powershell
cd backend
$env:DATABASE_URL = "postgresql://loganalyzer:changeme123@localhost:5432/loganalyzer"

# Appliquer toutes les migrations
alembic upgrade head

# Vérifier l'état
alembic current
alembic history
```

Migrations incluses :
- `001_normalized_schema` — tables `analyses` et `analysis_errors`
- `002_add_users_tenants` — tables `users` et `tenants`, colonnes `tenant_id`/`user_id` sur `analyses`

---

## 10. Kubernetes / Helm

### Prérequis

- `kubectl` + `helm` (≥ 3.15) installés
- Cluster K8s actif (Minikube, Kind, Docker Desktop K8s, ou cloud)

### Déploiement Minikube (dev)

```bash
minikube start --cpus=4 --memory=8192
eval $(minikube docker-env)

# Build des images localement
docker build -t ghcr.io/your-org/log-analyzer-backend:latest ./backend
docker build -t ghcr.io/your-org/log-analyzer-frontend:latest ./frontend

# Déployer le chart
helm upgrade --install log-analyzer helm/log-analyzer/ \
  --namespace log-analyzer \
  --create-namespace \
  --set "apiKey=testkey123" \
  --set "jwtSecretKey=local-dev-secret"

# Vérifier
kubectl get pods -n log-analyzer
kubectl get svc -n log-analyzer
```

### Déploiement production

```bash
helm upgrade --install log-analyzer helm/log-analyzer/ \
  --namespace log-analyzer \
  --create-namespace \
  -f helm/log-analyzer/values-prod.yaml \
  --set "apiKey=$API_KEY" \
  --set "jwtSecretKey=$JWT_SECRET_KEY" \
  --set "postgres.password=$POSTGRES_PASSWORD"
```

### Composants Helm déployés

| Template | Ressource |
|---|---|
| `backend/deployment.yaml` | Deployment (2 replicas par défaut) |
| `backend/hpa.yaml` | HPA — scale 2→6 à 70% CPU |
| `postgres/statefulset.yaml` | StatefulSet + PVC 10 Gi |
| `redis/deployment.yaml` | Deployment Redis |
| `chromadb/deployment.yaml` | Deployment + PVC 5 Gi |
| `ollama/deployment.yaml` | Deployment + PVC 20 Gi |
| `celery/deployment.yaml` | Deployment (2 replicas) |
| `frontend/deployment.yaml` | Deployment (1 replica) |
| `ingress.yaml` | Ingress nginx |
| `network-policy.yaml` | Isolation réseau par tier |

---

## 11. CI/CD — GitHub Actions + Jenkins

### GitHub Actions (`.github/workflows/ci.yml`)

Déclenché sur push/PR vers `main` :

| Job | Description |
|---|---|
| `frontend` | `npm ci` → tests → build → `npm audit` |
| `backend` | `pytest` + coverage XML avec PostgreSQL de service |
| `docker` | Build images → Trivy scan CRITICAL/HIGH |
| `sonarqube` | SonarQube scan (push seulement) |
| `helm-lint` | `helm lint` + `helm template` |

### Secrets GitHub requis

```
SONAR_TOKEN       → token SonarQube
SONAR_HOST_URL    → https://sonarqube.example.com
```

### Jenkins (Jenkinsfile)

Pipeline multibranch avec stages :

```
Checkout → Lint → Unit Tests → Build Docker → Trivy Scan
→ Push Registry → Deploy Staging → Smoke Test → Deploy Prod
```

Démarrer Jenkins en local :

```bash
docker compose -f jenkins/docker-compose.jenkins.yml up -d
```

---

## 12. SonarQube — qualité code

### Démarrer SonarQube localement

```bash
docker compose -f docker-compose.sonar.yml up -d
# Interface : http://localhost:9000 (admin/admin à la première connexion)
```

### Lancer l'analyse manuellement

```bash
# Générer la couverture backend
cd backend
coverage run -m pytest tests/ -v
coverage xml -o coverage.xml

# Générer la couverture frontend
cd frontend
npm test -- --coverage

# Lancer le scan Sonar
sonar-scanner \
  -Dsonar.host.url=http://localhost:9000 \
  -Dsonar.token=<votre-token>
```

Configuration dans [`sonar-project.properties`](file:///d:/downloads/log-analyzer-ai/sonar-project.properties).

---

## 13. Dépannage

### Ollama indisponible

| Symptôme | Action |
|---|---|
| `ollama_running: false` | `ollama serve` sur l'hôte |
| `model_available: false` | `ollama pull llama3.2` |
| Docker ne joint pas l'hôte | `OLLAMA_BASE_URL=http://host.docker.internal:11434` |

### Celery worker inactif

```bash
docker compose logs celery-worker --tail 50
# Vérifier que Redis est healthy
docker compose ps redis
```

### RAG non disponible

```bash
# Vérifier ChromaDB
curl http://localhost:8080/api/v1/heartbeat

# Ré-injecter les runbooks
docker compose exec backend python scripts/ingest_runbooks.py
```

### Erreur JWT 401

- Vérifier que le `JWT_SECRET_KEY` est identique entre les redémarrages
- Token expiré (durée : 2h) — se reconnecter via l'interface

### Base de données

```bash
# PostgreSQL
docker compose exec postgres psql -U loganalyzer -d loganalyzer \
  -c "SELECT COUNT(*) FROM analyses;"

# Migrations en attente
docker compose exec backend alembic current
docker compose exec backend alembic upgrade head
```

### Upload refusé (413)

Taille max : **10 Mo**. Variable `MAX_FILE_SIZE` dans `backend/core/config.py`.

### CORS

Variable : `CORS_ORIGINS=http://localhost:5173,http://localhost:3000`

---

## 14. Checklist soutenance

### Infrastructure

- [ ] `curl http://localhost:8000/health/ready` → HTTP 200
- [ ] `docker compose ps` → tous les services `Up (healthy)`
- [ ] Grafana accessible sur `:3001` avec dashboards Backend + Ollama

### Fonctionnalités

- [ ] Inscription → Login JWT fonctionnels (page de login)
- [ ] Upload sample log → résultats IA avec explication, causes, solutions
- [ ] RAG actif : analyser un log `connection timeout` → mention runbooks
- [ ] Analyse asynchrone : barre de progression SSE en temps réel
- [ ] Historique → Exporter PDF (rôle `analyst` ou `admin`)
- [ ] Rôle `viewer` → upload désactivé, export PDF masqué

### Observabilité

- [ ] Loki : requête `{container="log-analyzer-backend"}` dans Grafana
- [ ] Jaeger traces : `http://localhost:16686` → service `log-analyzer-backend`
- [ ] Prometheus alertes : `http://localhost:9090/alerts`

### CI/CD

- [ ] Tests unitaires passent : `pytest backend/tests/ -v`
- [ ] `helm lint helm/log-analyzer/` → aucune erreur

### Sécurité

- [ ] `API_KEY` / `JWT_SECRET_KEY` non committés (`.env` dans `.gitignore`)
- [ ] Isolation multi-tenant : analyses visibles par tenant seulement
