# Runbook — Erreurs Mémoire (OOM)

## Symptômes courants
- `OutOfMemoryError` / `MemoryError`
- `OOM killer` / `Killed process`
- `Cannot allocate memory`
- `memory usage exceeded`
- `java.lang.OutOfMemoryError: Java heap space`

## Diagnostic immédiat

### 1. Vérifier la consommation mémoire actuelle
```bash
free -h
top -o %MEM
# Docker
docker stats --no-stream
```

### 2. Identifier le processus consommateur
```bash
ps aux --sort=-%mem | head -20
# Kernel OOM log
dmesg | grep -i "out of memory"
journalctl -k | grep OOM
```

### 3. Analyser les memory leaks
```bash
# Python
import tracemalloc
tracemalloc.start()
# ... code ...
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

# Java heap dump
jmap -dump:format=b,file=heap.hprof <pid>
```

## Causes fréquentes
1. **Memory leak applicatif** — objets non libérés en mémoire
2. **Trop de workers/threads** — chaque worker consomme de la RAM
3. **Cache non borné** — cache qui grossit indéfiniment
4. **Fichiers trop grands en RAM** — lecture de fichier entier sans streaming
5. **Limite mémoire Docker trop basse** — `--memory` trop restrictif
6. **Fuite dans une bibliothèque tierce** — souvent en ML/IA

## Solutions recommandées
1. Augmenter la RAM du serveur ou les limites Docker (`--memory 2g`)
2. Implémenter le streaming pour les gros fichiers
3. Borner les caches (`maxsize=1000` dans `functools.lru_cache`)
4. Profiler la mémoire avec `memory_profiler` (Python) ou `MAT` (Java)
5. Activer le garbage collector explicitement dans les boucles longues
6. Utiliser des générateurs Python au lieu de listes pour les grands datasets
7. Configurer `MALLOC_TRIM_THRESHOLD_` pour libérer la RAM au runtime

## Configuration Docker recommandée
```yaml
deploy:
  resources:
    limits:
      memory: 2G
    reservations:
      memory: 512M
```

## Métriques à surveiller
- `container_memory_usage_bytes`
- `process_resident_memory_bytes`
- `python_gc_objects_collected_total`
