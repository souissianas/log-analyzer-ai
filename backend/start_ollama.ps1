# Script de démarrage d'Ollama sur port 11435
# Utilisation: .\start_ollama.ps1

Write-Host "🚀 Démarrage d'Ollama sur port 11435..." -ForegroundColor Green

# Définir le port personnalisé
$env:OLLAMA_HOST = "127.0.0.1:11435"

# Attendre que l'ancien processus soit libéré
Write-Host "⏳ Attente de 2 secondes..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

# Lancer Ollama
Write-Host "▶️  Démarrage de Ollama..." -ForegroundColor Cyan
ollama serve
