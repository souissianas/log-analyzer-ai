# Frontend - Log Analyzer AI

Simple frontend React (Vite) pour la Semaine 6: upload et affichage des analyses IA.

Install:

```bash
cd frontend
npm install
```

Dev:

```bash
npm run dev
```

Le frontend communique avec le backend sur `http://localhost:8000`.

Notes:
- Endpoint utilisé: `/ollama/analyze-file?output_format=json`
- CORS: le backend autorise `*`.
