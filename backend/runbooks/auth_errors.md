# Runbook — Erreurs d'Authentification

## Symptômes courants
- `authentication failed`
- `invalid user` / `invalid credentials`
- `failed password for`
- `credentials not found`
- `Access denied for user`
- `401 Unauthorized` / `403 Forbidden`

## Diagnostic

### 1. Vérifier les logs d'authentification
```bash
# SSH
journalctl -u sshd | grep "Failed"
grep "Failed password" /var/log/auth.log

# PostgreSQL
grep "authentication failed" /var/log/postgresql/postgresql-*.log

# Application
grep -i "auth\|401\|403\|denied" /var/log/app.log
```

### 2. Vérifier la validité des credentials
```bash
# Test connexion DB
psql -U loganalyzer -h localhost -d loganalyzer -c "SELECT 1"

# Test API key
curl -H "X-API-Key: $API_KEY" http://localhost:8000/health
```

### 3. Détecter une attaque par brute-force
```bash
grep "Failed password" /var/log/auth.log | awk '{print $11}' | sort | uniq -c | sort -rn | head
# IPs les plus actives
```

## Causes fréquentes
1. **Mot de passe expiré** — politiques de rotation non respectées
2. **Variable d'environnement manquante** — `API_KEY` non définie
3. **Token JWT expiré** — TTL trop court ou horloge désynchronisée
4. **Mauvais utilisateur DB** — DATABASE_URL mal configurée
5. **Brute-force / credential stuffing** — attaque externe
6. **Changement de secret sans redéploiement** — secret rotaté mais app non redémarrée

## Solutions recommandées
1. Vérifier les variables d'environnement : `env | grep -i key\|password\|secret`
2. Régénérer et redéployer les secrets : Docker secrets / GitHub Secrets
3. Activer le rate limiting sur les endpoints d'authentification
4. Configurer fail2ban pour bloquer les IPs après N échecs
5. Synchroniser les horloges NTP (JWT sensible à la dérive temporelle)
6. Activer MFA si disponible

## Sécurisation fail2ban — exemple
```ini
[log-analyzer-api]
enabled = true
filter = log-analyzer-auth
logpath = /var/log/log-analyzer/access.log
maxretry = 5
bantime = 3600
findtime = 600
```

## Métriques à surveiller
- `http_requests_total{status="401"}` rate
- `http_requests_total{status="403"}` rate
- Nombre d'IPs uniques sur `/auth/login`
