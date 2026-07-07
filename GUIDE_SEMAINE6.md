# 🚀 GUIDE RAPIDE SEMAINE 6 : Interface React

## 📋 Rappel de ce qui fonctionne

✅ **Backend complet et testé:**
- Ollama sur port 11435
- FastAPI sur port 8000
- Endpoints: `/ollama/health`, `/ollama/analyze-line`, `/ollama/analyze-file`
- Llama 3.2 génère: Explication + Causes + Solutions

## 🎯 Semaine 6 : Créer une Interface Web

### Plan (2-3 jours)

#### **Jour 1: Setup React + Interface Upload**
1. Créer projet Vite + React
2. Composant upload fichier log
3. Affichage des résultats en JSON

#### **Jour 2: Affichage + Styles**
1. Parser JSON résultats
2. Afficher erreurs avec couleurs
3. Mettre en valeur: Explication + Causes + Solutions
4. CSS / Tailwind

#### **Jour 3: Tests + Finalisation**
1. Tester upload/analyse complet
2. Gestion erreurs
3. Loader pendant l'analyse
4. Export résultats

---

## 📂 Structure Finale

```
log-analyzer-ai/
├── backend/              (Semaine 1-5) ✅
│   ├── main.py
│   ├── services/
│   ├── sample_logs/
│   └── requirements.txt
├── frontend/             (Semaine 6) 🚀
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   └── styles/
│   ├── package.json
│   └── vite.config.js
└── docs/
    ├── SEMAINE5_RAPPORT.md
    └── GUIDE_SEMAINE6.md
```

---

## 💡 Code pour démarrer Semaine 6

### Step 1: Créer le projet React
```bash
# Terminal 1
cd d:\downloads\log-analyzer-ai
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm run dev
```

### Step 2: Créer composant upload
```jsx
// frontend/src/App.jsx
import { useState } from 'react';
import LogUploader from './components/LogUploader';
import ErrorAnalysis from './components/ErrorAnalysis';

function App() {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleAnalyze = async (file) => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('max_errors', 5);
      
      const res = await fetch('http://127.0.0.1:8000/ollama/analyze-file', {
        method: 'POST',
        body: formData,
      });
      
      const data = await res.json();
      setResults(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <h1>🧠 Log Analyzer AI</h1>
      <LogUploader onAnalyze={handleAnalyze} disabled={loading} />
      {loading && <p>⏳ Analyse en cours...</p>}
      {results && <ErrorAnalysis data={results} />}
    </div>
  );
}

export default App;
```

### Step 3: Afficher les résultats
```jsx
// frontend/src/components/ErrorAnalysis.jsx
export default function ErrorAnalysis({ data }) {
  return (
    <div className="results">
      <h2>📊 Résultats</h2>
      <p>Erreurs: {data.total_errors_found} détectées, {data.total_analyzed} analysées</p>
      
      {data.analyzed.map((error) => (
        <div key={error.index} className="error-card">
          <h3>Erreur #{error.index}</h3>
          <p><strong>Type:</strong> {error.level}</p>
          <p><strong>Message:</strong> {error.message}</p>
          
          {error.success && error.analysis && (
            <>
              <div className="explanation">
                <h4>📌 Explication</h4>
                <p>{error.analysis.explanation}</p>
              </div>
              
              <div className="causes">
                <h4>⚠️ Causes</h4>
                <ul>
                  {error.analysis.causes.map((cause, i) => (
                    <li key={i}>{cause}</li>
                  ))}
                </ul>
              </div>
              
              <div className="solutions">
                <h4>💡 Solutions</h4>
                <ul>
                  {error.analysis.solutions.map((sol, i) => (
                    <li key={i}>{sol}</li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
```

---

## 🔌 Vérifier Backend est prêt

```powershell
# Terminal 1: Ollama
$env:OLLAMA_HOST = "127.0.0.1:11435"
ollama serve

# Terminal 2: FastAPI
cd backend
$env:PYTHONPATH="D:\downloads\log-analyzer-ai\backend"
python -m uvicorn main:app --reload --port 8000

# Terminal 3: React
cd frontend
npm run dev
```

---

## 🎨 Styles Recommandés (Tailwind)

```bash
# Dans le dossier frontend
npm install -D tailwindcss
npx tailwindcss init -p
```

```jsx
// Exemple d'erreur stylisée
<div className="bg-red-50 border-l-4 border-red-500 p-4 my-2">
  <h4 className="text-red-800 font-bold">🔴 {level}</h4>
  <p className="text-red-700">{message}</p>
</div>
```

---

## 📞 Aide Semaine 6

- **Upload ne marche pas?** → Vérifier CORS dans main.py (déjà activé ✅)
- **Résultats pas beaux?** → Ajouter Tailwind ou CSS custom
- **Lenteur?** → Afficher loader, limiter max_errors
- **Erreurs réseau?** → Vérifier http://127.0.0.1:8000/health

---

**Bonne chance pour la Semaine 6!** 🚀  
*N'hésitez pas si vous avez des questions.*
