# Guide de soutenance - Log Analyzer AI

## 1. Pitch court

Log Analyzer AI est une application web qui permet d'uploader un fichier de logs, de detecter automatiquement les erreurs critiques, puis de demander a une IA locale d'expliquer chaque erreur avec ses causes possibles et ses solutions recommandees.

## 2. Demonstration conseillee

### Etape 1 - Montrer l'architecture

Presenter rapidement :

- React pour l'interface,
- FastAPI pour l'API,
- Ollama / Llama 3.2 pour l'analyse IA,
- PostgreSQL ou SQLite pour la sauvegarde,
- Docker Compose pour lancer les services.

### Etape 2 - Lancer les services

Ollama sur la machine :

```powershell
ollama serve
```

Docker :

```powershell
cd D:\downloads\log-analyzer-ai
docker compose up --build
```

Ou lancement local :

```powershell
cd D:\downloads\log-analyzer-ai\backend
python -m uvicorn main:app --reload --port 8000
```

```powershell
cd D:\downloads\log-analyzer-ai\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### Etape 3 - Verifier la sante

Backend :

```powershell
curl http://127.0.0.1:8000/health
```

Ollama :

```powershell
curl http://127.0.0.1:8000/ollama/health
```

### Etape 4 - Montrer l'interface

Frontend local :

```text
http://127.0.0.1:5173/
```

Frontend Docker :

```text
http://localhost:3000
```

Actions :

1. Verifier Backend OK et Ollama OK.
2. Uploader un fichier `.log`.
3. Choisir le nombre d'erreurs a analyser.
4. Cliquer sur `Analyser avec IA`.
5. Presenter les cartes d'erreurs.
6. Expliquer les sections :
   - Explication,
   - Causes possibles,
   - Solutions recommandees.
7. Montrer l'historique.
8. Montrer l'export PDF si disponible.

## 3. Test final a executer

Avec le backend actif :

```powershell
cd D:\downloads\log-analyzer-ai\backend
python test_semaine8_smoke.py
```

Ce test valide :

- backend disponible,
- Ollama disponible,
- upload de fichier,
- analyse IA,
- format structure,
- sauvegarde dans l'historique.

## 4. Points techniques a expliquer

- Le parser ne garde que les niveaux critiques.
- Le prompt demande un JSON strict.
- Le backend normalise la reponse IA pour eviter les problemes de format.
- L'interface ne depend pas du texte brut, mais d'un contrat stable :

```json
{
  "explanation": "...",
  "causes": ["..."],
  "solutions": ["..."]
}
```

## 5. Questions possibles

**Pourquoi Ollama ?**

Pour executer le modele localement sans envoyer les logs a un service externe.

**Pourquoi Docker ?**

Pour rendre l'installation reproductible : base de donnees, backend et frontend sont lances ensemble.

**Pourquoi limiter le nombre d'erreurs analysees ?**

Chaque analyse IA prend du temps. La limite permet de garder une experience fluide.

**Que se passe-t-il si Ollama ne repond pas ?**

Le backend retourne une erreur claire et l'interface l'affiche.

**Comment ameliorer le projet ?**

- ajouter authentification,
- analyser plus de formats de logs,
- ajouter streaming des reponses IA,
- ajouter un tableau de bord statistique,
- lancer Ollama directement en conteneur si la machine le permet.

## 6. Conclusion orale

Le projet est une chaine complete de diagnostic de logs : detection, analyse IA, affichage, sauvegarde et export. Il peut etre utilise comme base pour un outil d'aide au support technique ou au monitoring applicatif.
