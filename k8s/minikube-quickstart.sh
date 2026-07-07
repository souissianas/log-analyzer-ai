#!/usr/bin/env bash
# =============================================================================
#  minikube-quickstart.sh — Log Analyzer AI
#  Lance un cluster Minikube complet avec le chart Helm en une commande.
#  Usage: bash k8s/minikube-quickstart.sh
# =============================================================================
set -euo pipefail

NAMESPACE="log-analyzer"
RELEASE="log-analyzer"
CHART_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../helm/log-analyzer" && pwd)"

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
RESET="\033[0m"

info()    { echo -e "${GREEN}[INFO]${RESET}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*"; exit 1; }

# ── Pré-requis ────────────────────────────────────────────────────────────────
check_deps() {
  local missing=()
  for cmd in minikube kubectl helm docker; do
    command -v "$cmd" &>/dev/null || missing+=("$cmd")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    error "Dépendances manquantes : ${missing[*]}\nInstaller via: https://minikube.sigs.k8s.io/docs/start/"
  fi
}

# ── Minikube ──────────────────────────────────────────────────────────────────
start_minikube() {
  if minikube status --format='{{.Host}}' 2>/dev/null | grep -q "Running"; then
    info "Minikube déjà démarré — on continue."
  else
    info "Démarrage de Minikube (4 CPU, 8 Gi RAM)…"
    minikube start \
      --cpus=4 \
      --memory=8192 \
      --disk-size=30g \
      --driver=docker \
      --addons=ingress,metrics-server
  fi

  info "Activation du contexte Docker sur Minikube…"
  eval "$(minikube docker-env)"
}

# ── Build des images ─────────────────────────────────────────────────────────
build_images() {
  local ROOT
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

  info "Build image backend…"
  docker build -t ghcr.io/your-org/log-analyzer-backend:latest "$ROOT/backend"

  info "Build image frontend…"
  docker build -t ghcr.io/your-org/log-analyzer-frontend:latest "$ROOT/frontend"
}

# ── Helm deploy ───────────────────────────────────────────────────────────────
deploy_chart() {
  info "Déploiement du chart Helm '$RELEASE' dans le namespace '$NAMESPACE'…"

  helm upgrade --install "$RELEASE" "$CHART_DIR" \
    --namespace "$NAMESPACE" \
    --create-namespace \
    --set "apiKey=minikube-dev-key" \
    --set "jwtSecretKey=minikube-jwt-secret" \
    --set "postgres.password=changeme123" \
    --set "backend.image.pullPolicy=Never" \
    --set "frontend.image.pullPolicy=Never" \
    --wait \
    --timeout=10m

  info "Déploiement terminé."
}

# ── Vérifications ─────────────────────────────────────────────────────────────
verify() {
  info "Pods dans le namespace '$NAMESPACE' :"
  kubectl get pods -n "$NAMESPACE" -o wide

  echo ""
  info "Services :"
  kubectl get svc -n "$NAMESPACE"

  echo ""
  # Attendre backend ready
  info "Attente du backend (jusqu'à 120s)…"
  kubectl rollout status deployment/log-analyzer-backend -n "$NAMESPACE" --timeout=120s || \
    warn "Le backend n'est pas encore prêt. Relancer : kubectl rollout status deployment/log-analyzer-backend -n $NAMESPACE"

  echo ""
  # URL d'accès
  local BACKEND_URL
  BACKEND_URL=$(minikube service log-analyzer-backend -n "$NAMESPACE" --url 2>/dev/null || echo "non disponible")
  local FRONTEND_URL
  FRONTEND_URL=$(minikube service log-analyzer-frontend -n "$NAMESPACE" --url 2>/dev/null || echo "non disponible")

  echo ""
  echo -e "${GREEN}═══════════════════════════════════════════════════${RESET}"
  echo -e "${GREEN}  Log Analyzer AI — Minikube prêt !${RESET}"
  echo -e "${GREEN}═══════════════════════════════════════════════════${RESET}"
  echo -e "  Frontend  : ${YELLOW}${FRONTEND_URL}${RESET}"
  echo -e "  Backend   : ${YELLOW}${BACKEND_URL}${RESET}"
  echo -e "  Health    : ${YELLOW}${BACKEND_URL}/health/ready${RESET}"
  echo ""
  echo -e "  Dashboard K8s : ${YELLOW}minikube dashboard${RESET}"
  echo -e "  Logs backend  : ${YELLOW}kubectl logs -n $NAMESPACE -l app=log-analyzer-backend -f${RESET}"
  echo -e "${GREEN}═══════════════════════════════════════════════════${RESET}"
}

# ── Teardown (option --clean) ─────────────────────────────────────────────────
teardown() {
  warn "Suppression du release Helm '$RELEASE'…"
  helm uninstall "$RELEASE" -n "$NAMESPACE" 2>/dev/null || true
  kubectl delete namespace "$NAMESPACE" 2>/dev/null || true
  info "Namespace '$NAMESPACE' supprimé."
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
  if [[ "${1:-}" == "--clean" ]]; then
    teardown
    exit 0
  fi

  check_deps
  start_minikube
  build_images
  deploy_chart
  verify
}

main "$@"
