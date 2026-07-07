# Runbook — Erreurs Disque

## Symptômes courants
- `No space left on device`
- `disk full` / `ENOSPC`
- `Structure needs cleaning`
- `Input/output error`
- `Read-only file system`

## Diagnostic immédiat

### 1. Vérifier l'espace disque
```bash
df -h              # espace disque par partition
df -i              # inodes (peut être plein même avec de l'espace)
du -sh /var/log/*  # plus gros répertoires
du -sh /tmp/*
```

### 2. Trouver les gros fichiers
```bash
find / -xdev -size +100M -exec ls -lh {} \; 2>/dev/null | sort -k5 -rh | head -20
# Docker
docker system df
docker system prune -f
```

### 3. Vérifier les logs Docker/système
```bash
journalctl --disk-usage
ls -lh /var/lib/docker/containers/*/
```

## Causes fréquentes
1. **Logs applicatifs non rotatés** — `/var/log` plein
2. **Fichiers temporaires accumulés** — `/tmp` non nettoyé
3. **Images Docker orphelines** — volumes et images inutilisés
4. **Base de données qui grossit** — WAL PostgreSQL, binlogs MySQL
5. **Core dumps** — crashs répétés laissent des fichiers core
6. **Inodes épuisés** — trop de petits fichiers (common avec npm/node_modules)

## Solutions recommandées
1. Nettoyer les logs : `truncate -s 0 /var/log/app.log` ou configurer `logrotate`
2. Nettoyer Docker : `docker system prune -af --volumes`
3. Nettoyer /tmp : `find /tmp -mtime +7 -delete`
4. PostgreSQL WAL : `VACUUM FULL` + archivage WAL
5. Augmenter la taille du volume (EBS resize, LVM extend)
6. Configurer une rotation de logs dans l'application

## Rotation de logs — exemple logrotate
```
/var/log/log-analyzer/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    sharedscripts
    postrotate
        systemctl reload log-analyzer
    endscript
}
```

## Métriques à surveiller
- `node_filesystem_avail_bytes` (< 10% → alerte)
- `node_filesystem_files_free` (inodes)
- `container_fs_usage_bytes`
