# Performance — pourquoi une analyse peut prendre 30s+ et comment l'accélérer

## Pourquoi un petit fichier (quelques Ko) peut quand même prendre 30s+

Le temps d'analyse n'est presque jamais dû à la taille du fichier : parser
et classifier quelques Ko de logs prend quelques millisecondes. Le temps
part presque entièrement dans les appels au modèle Ollama (LLM), qui sont
lents par nature sur CPU. Trois facteurs se cumulent typiquement :

1. **Un appel Ollama par erreur détectée, en série.** Avant les correctifs
   ci-dessous, la route legacy `/ollama/analyze-file` attendait la fin
   d'une analyse avant de lancer la suivante. 5 erreurs × ~5-8s chacune =
   25-40s, même sur un tout petit fichier.
2. **Le "cold start" du modèle.** Si Ollama a déchargé le modèle de la RAM
   (par défaut après 5 min d'inactivité), le premier appel doit d'abord le
   recharger — plusieurs secondes de plus, invisibles dans les logs
   applicatifs.
3. **RAG activé par défaut.** Chaque appel structuré déclenche une
   recherche RAG (embedding + requête ChromaDB) avant même d'appeler le
   modèle principal, ajoutant 1-2s par erreur.

## Ce qui a été corrigé dans le code

- **`services/ollama_service.py`** : `num_predict` réduit de 200 → 150
  tokens (configurable via `OLLAMA_NUM_PREDICT`), et `keep_alive` ajouté
  (`OLLAMA_KEEP_ALIVE`, 30 min par défaut) pour garder le modèle chargé en
  RAM entre deux analyses.
- **`main.py`** : le modèle est maintenant pré-chargé ("pre-warm") au
  démarrage du backend, en tâche de fond, pour que le premier utilisateur
  de la journée ne paie pas le coût de chargement du modèle.
- **`routers/ollama.py`** (`/ollama/analyze-file`) : la route legacy
  applique maintenant les mêmes optimisations que le pipeline asynchrone
  (`worker.py`) :
  - déduplication des messages d'erreur identiques (une seule analyse par
    signature, pas par occurrence) ;
  - vérification du cache DB (`get_cached_error_analysis`) avant tout
    appel Ollama ;
  - parallélisme borné (3 appels concurrents max) au lieu d'une boucle
    séquentielle ;
  - RAG désactivé par défaut sur cette route (déjà le cas côté worker).
- **`backend/start_ollama.ps1`** : définit `OLLAMA_NUM_PARALLEL=3` côté
  serveur Ollama. **Important** : sans ce réglage, même si l'application
  envoie 3 requêtes "en parallèle", Ollama les traite une par une côté
  serveur et le gain de parallélisation applicatif est perdu.
  Ce script concerne le **dev local sans Docker** (Ollama sur l'hôte,
  port 11435). Si tu utilises `docker-compose.yml` (`start.ps1` option 1),
  Ollama tourne déjà dans son propre conteneur (`log-analyzer-ollama`,
  port 11434) avec `OLLAMA_NUM_PARALLEL=4` et `OLLAMA_KEEP_ALIVE=30m`
  déjà configurés — rien à faire de plus de ce côté.

## Ce que tu peux encore ajuster selon ta machine

- **Utilise le flux asynchrone (`/jobs/analyze`) plutôt que
  `/ollama/analyze-file`** si ce n'est pas déjà le cas : le frontend
  (`App.jsx`) l'utilise déjà par défaut, mais si tu appelles l'API
  directement (curl, script, Postman), privilégie `/jobs/analyze` +
  `/jobs/{id}/stream` pour profiter du cache + dédup + parallélisme.
- **CPU vs GPU** : sur CPU seul, `llama3.2` (3B) reste lent (plusieurs
  secondes par génération). Si ta machine a un GPU compatible, assure-toi
  qu'Ollama l'utilise (`ollama ps` doit indiquer `100% GPU`, pas `100% CPU`).
- **Modèle plus léger pour la démo** : si la précision de `llama3.2:3b`
  n'est pas critique, `llama3.2:1b` est nettement plus rapide (`ollama pull
  llama3.2:1b` puis `OLLAMA_MODEL=llama3.2:1b`).
- **`max_errors`** : limite le nombre d'erreurs analysées par fichier côté
  appel API (`?max_errors=5`) si tu n'as pas besoin d'analyser toutes les
  occurrences.

## Limite connue

Le cache (`get_cached_error_analysis`) ne fonctionne que pour des messages
d'erreur strictement identiques (même texte). Deux erreurs proches mais pas
identiques (ex. un ID de requête différent dans le message) seront
analysées séparément. Un futur axe d'amélioration serait de normaliser les
messages (retirer IDs/timestamps variables) avant de calculer la clé de
cache.