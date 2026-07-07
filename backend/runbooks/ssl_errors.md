# Runbook — Erreurs SSL/TLS et Certificats

## Symptômes courants
- `SSL certificate problem`
- `certificate verify failed`
- `SNI does not match`
- `SSL handshake failed`
- `certificate has expired`
- `unable to verify the first certificate`

## Diagnostic

### 1. Inspecter le certificat
```bash
# Vérifier expiration et SAN
openssl s_client -connect <host>:<port> -servername <host> </dev/null 2>&1 | \
  openssl x509 -noout -text | grep -E "Subject|Issuer|Not After|DNS:"

# Date d'expiration uniquement
echo | openssl s_client -connect <host>:443 2>/dev/null | \
  openssl x509 -noout -enddate
```

### 2. Valider la chaîne de certificats
```bash
openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt server.crt
# ou avec curl
curl -v https://<host>/ 2>&1 | grep -A5 "SSL"
```

### 3. Vérifier la cohérence SNI/hostname
```bash
# Le CN ou SAN doit correspondre au hostname appelé
openssl s_client -connect <host>:<port> -servername <host> 2>&1 | grep "CN ="
```

## Causes fréquentes
1. **Certificat expiré** — auto-renouvellement Let's Encrypt échoué
2. **SNI non configuré** — reverse proxy ne transmet pas le bon hostname
3. **Chaîne incomplète** — certificat intermédiaire manquant
4. **Certificat auto-signé** — non reconnu par les clients
5. **Mauvaise CA** — certificat signé par une CA non faite de confiance
6. **Horloge désynchronisée** — le certificat semble invalide côté client

## Solutions recommandées

### Renouveler Let's Encrypt
```bash
certbot renew --force-renewal
systemctl reload nginx
```

### Générer un certificat de développement (mkcert)
```bash
mkcert -install
mkcert localhost 127.0.0.1
```

### Configurer nginx avec TLS
```nginx
server {
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/<domain>/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/<domain>/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    add_header Strict-Transport-Security "max-age=31536000" always;
}
```

## Métriques à surveiller
- Expiration du certificat (alerte à J-30, J-14, J-7)
- `ssl_handshake_errors_total`
- Uptime de certbot.timer (`systemctl status certbot.timer`)
