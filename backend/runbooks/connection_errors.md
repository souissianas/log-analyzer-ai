# Runbook — Erreurs de Connexion

## Symptômes courants
- `connection refused` / `ECONNREFUSED`
- `connection timed out` / `timeout`
- `failed to connect to host`
- `no route to host`
- `connection reset by peer`

## Diagnostic

### 1. Vérifier que le service cible est en cours d'exécution
```bash
systemctl status <service>
# ou
docker ps | grep <container>
```

### 2. Vérifier la connectivité réseau
```bash
ping <host>
telnet <host> <port>
curl -v http://<host>:<port>/health
```

### 3. Vérifier les règles firewall
```bash
iptables -L -n | grep <port>
ufw status
```

### 4. Vérifier les ressources système
```bash
ss -tulnp | grep <port>   # port en écoute ?
netstat -an | grep TIME_WAIT   # trop de connexions en attente ?
```

## Causes fréquentes
1. **Service arrêté** — le service cible n'est pas démarré ou a crashé
2. **Port incorrect** — mauvaise configuration du port dans l'application
3. **Firewall bloquant** — règle iptables ou groupe de sécurité cloud
4. **Pool de connexions saturé** — trop de connexions simultanées
5. **Timeout réseau trop court** — augmenter `connect_timeout` dans la config
6. **DNS non résolu** — vérifier `/etc/resolv.conf` et les records DNS
7. **Docker réseau** — container sur un réseau différent

## Solutions recommandées
1. Redémarrer le service cible : `systemctl restart <service>`
2. Augmenter le pool de connexions dans la config de l'application
3. Vérifier et corriger la configuration du firewall
4. Implémenter un circuit breaker (Hystrix, Resilience4j)
5. Configurer des health checks et restart policies Docker
6. Ajouter retry logic avec exponential backoff dans le client

## Métriques à surveiller
- `connection_errors_total` — compteur d'erreurs de connexion
- `connection_pool_size` vs `connection_pool_used`
- `tcp_connection_refused_total`
