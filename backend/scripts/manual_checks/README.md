# Manual Verification Scripts

Ce dossier contient les scripts de test et de validation manuelle du backend.

> [!NOTE]
> Cette suite de scripts n'est pas exécutée par la suite de tests automatisés officielle (située sous `backend/tests/`).
> Ces fichiers servent uniquement pour des vérifications interactives et manuelles.

## Contenu

- `test_analyze_file.py` : Test de l'analyse globale de fichier
- `test_analyze_line.py` : Test de l'analyse d'une seule ligne de log
- `test_integration_upload.py` : Test d'intégration de l'upload
- `test_ollama.py` : Test d'appel direct aux APIs d'Ollama
- `test_ollama_nested_explanation.py` : Test des réponses imbriquées d'Ollama
- `test_ollama_normalization.py` : Test de normalisation des réponses d'Ollama
- `test_semaine5.py` / `test_semaine5_fast.py` : Tests liés aux features de la semaine 5
- `test_semaine6_structured_explanations.py` : Tests pour la structuration de l'explication
- `test_semaine8_smoke.py` : Smoke test de la semaine 8
- `test_upload.py` : Vérification du endpoint d'upload
- `test_whatsapp.py` : Validation de l'intégration avec Twilio/WhatsApp
