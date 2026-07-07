#!/usr/bin/env pwsh
# 🚀 SCRIPT DE DÉMARRAGE RAPIDE - LOG ANALYZER AI
# Semaine 5: Intégration Ollama + PostgreSQL
#
# Correction apportée :
#   Le message "N'oubliez pas: Ollama doit tourner sur la machine hôte"
#   était devenu FAUX : docker-compose.yml inclut désormais son propre
#   service `ollama` (conteneur log-analyzer-ollama, port 11434, avec
#   OLLAMA_NUM_PARALLEL=4 et OLLAMA_KEEP_ALIVE=30m déjà configurés).
#   `docker-compose up -d` suffit donc à tout démarrer, Ollama inclus.
#   L'option 2 vérifie maintenant aussi Redis et le worker Celery, dont
#   dépend le flux d'analyse asynchrone /jobs/analyze — avant, seuls
#   Backend/Ollama/PostgreSQL étaient contrôlés, alors qu'un Celery
#   absent fait échouer silencieusement toute analyse via /jobs.
#
# Note : si tu développes en LOCAL sans Docker (backend lancé via
# `uvicorn main:app` directement, avec SQLite), utilise plutôt
# backend/start_ollama.ps1 pour démarrer Ollama sur l'hôte (port 11435).

Write-Host ""
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  🚀 LOG ANALYZER AI - SEMAINE 5" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Menu
Write-Host "Sélectionnez une action:" -ForegroundColor Yellow
Write-Host "1) Démarrer Docker (PostgreSQL + Backend + Ollama + Redis + Celery)"
Write-Host "2) Vérifier la santé du système"
Write-Host "3) Lancer les tests"
Write-Host "4) Arrêter les services"
Write-Host "5) Voir les logs du backend"
Write-Host "0) Quitter"
Write-Host ""

$choice = Read-Host "Votre choix (0-5)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "▶ Démarrage de Docker Compose..." -ForegroundColor Green
        docker-compose up -d
        Write-Host ""
        Write-Host "⏳ Attente du démarrage d'Ollama (peut prendre 30-60s au premier lancement" -ForegroundColor Yellow
        Write-Host "   le temps que ollama-init télécharge les modèles llama3.2 + nomic-embed-text)..." -ForegroundColor Yellow

        $ollamaReady = $false
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 2
            Try {
                Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -ErrorAction Stop | Out-Null
                $ollamaReady = $true
                break
            } Catch {
                Write-Host "." -NoNewline -ForegroundColor Gray
            }
        }
        Write-Host ""

        if ($ollamaReady) {
            Write-Host "✓ Ollama prêt (port 11434, conteneur log-analyzer-ollama)" -ForegroundColor Green
        } else {
            Write-Host "⚠  Ollama pas encore prêt — vérifie avec: docker logs log-analyzer-ollama-init" -ForegroundColor Yellow
        }
        Write-Host "✓ Docker démarré (PostgreSQL, Redis, Ollama, Backend, Celery, Frontend)" -ForegroundColor Green
        Write-Host ""
    }

    "2" {
        Write-Host ""
        Write-Host "▶ Vérification de la santé..." -ForegroundColor Green

        # Backend
        Try {
            $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -ErrorAction Stop
            Write-Host "✓ Backend: OK (port 8000)" -ForegroundColor Green
        } Catch {
            Write-Host "✗ Backend: Non accessible" -ForegroundColor Red
        }

        # Ollama (via le backend, et directement)
        Try {
            $r = Invoke-WebRequest -Uri "http://localhost:8000/ollama/health" -ErrorAction Stop
            $health = $r.Content | ConvertFrom-Json
            Write-Host "✓ Ollama: Running (modèle: $($health.required_model))" -ForegroundColor Green
        } Catch {
            Write-Host "✗ Ollama: Non disponible" -ForegroundColor Red
        }

        # PostgreSQL
        Try {
            docker exec log-analyzer-postgres pg_isready -U loganalyzer > $null 2>&1
            Write-Host "✓ PostgreSQL: Ready (port 5432)" -ForegroundColor Green
        } Catch {
            Write-Host "✗ PostgreSQL: Non accessible" -ForegroundColor Red
        }

        # Redis — requis par Celery pour le flux /jobs/analyze
        Try {
            $redisPing = docker exec log-analyzer-redis redis-cli ping 2>&1
            if ($redisPing -match "PONG") {
                Write-Host "✓ Redis: Ready (port 6379)" -ForegroundColor Green
            } else {
                Write-Host "✗ Redis: Non accessible" -ForegroundColor Red
            }
        } Catch {
            Write-Host "✗ Redis: Non accessible (conteneur log-analyzer-redis introuvable ?)" -ForegroundColor Red
        }

        # Worker Celery — sans lui, /jobs/analyze répond 503
        Try {
            $celeryLog = docker logs log-analyzer-celery --tail 10 2>&1
            if ($celeryLog -match "ready|celery@") {
                Write-Host "✓ Celery worker: Running" -ForegroundColor Green
            } else {
                Write-Host "⚠  Celery worker: statut incertain, vérifie 'docker logs log-analyzer-celery'" -ForegroundColor Yellow
            }
        } Catch {
            Write-Host "✗ Celery worker: Non accessible (conteneur log-analyzer-celery introuvable ?)" -ForegroundColor Red
        }

        # ChromaDB — requis pour le RAG (runbooks)
        Try {
            docker exec log-analyzer-chromadb python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/heartbeat', timeout=3)" > $null 2>&1
            Write-Host "✓ ChromaDB: Ready (port 8080 hôte / 8000 interne)" -ForegroundColor Green
        } Catch {
            Write-Host "✗ ChromaDB: Non accessible" -ForegroundColor Red
        }

        Write-Host ""
    }

    "3" {
        Write-Host ""
        Write-Host "▶ Lancement des tests..." -ForegroundColor Green
        Write-Host ""

        cd backend
        Write-Host "Exécution: python test_semaine5_fast.py" -ForegroundColor Cyan
        python test_semaine5_fast.py
        cd ..

        Write-Host ""
    }

    "4" {
        Write-Host ""
        Write-Host "▶ Arrêt des services..." -ForegroundColor Green
        docker-compose down
        Write-Host "✓ Services arrêtés" -ForegroundColor Green
        Write-Host ""
    }

    "5" {
        Write-Host ""
        Write-Host "▶ Logs du backend (derniers 30 lignes):" -ForegroundColor Green
        Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
        docker logs log-analyzer-backend --tail 30
        Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
        Write-Host ""
    }

    "0" {
        Write-Host "Au revoir! 👋" -ForegroundColor Cyan
        Exit
    }

    default {
        Write-Host "Option invalide" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Appuyez sur une touche pour continuer..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")