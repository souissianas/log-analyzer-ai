"""
services/rag_service.py
RAG (Retrieval-Augmented Generation) via ChromaDB + Ollama embeddings.

Corrections appliquées :
  1. Port ChromaDB défaut changé 8000 → 8001 (évite le conflit avec FastAPI :8000)
  2. CHROMADB_URL supprimé (variable construite mais jamais utilisée)
  3. Seuil de similarité réduit 1.5 → 0.8 (élimine les runbooks non pertinents)
  4. Log d'avertissement ajouté si nomic-embed-text n'est pas disponible
  5. Gestion d'erreur renforcée dans _get_client() avec retry=False pour éviter
     des tentatives répétées sur un ChromaDB absent
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────
CHROMADB_HOST = os.environ.get("CHROMADB_HOST", "localhost")

# FIX 1 : port 8001 par défaut (plus 8000) pour éviter le conflit avec FastAPI.
# Dans docker-compose.yml, s'assurer que chromadb expose bien le port 8001 :
#   chromadb:
#     image: chromadb/chroma
#     ports:
#       - "8001:8000"   ← hôte:conteneur
# Et dans .env : CHROMADB_PORT=8001
CHROMADB_PORT = int(os.environ.get("CHROMADB_PORT", "8001"))

# FIX 2 : CHROMADB_URL supprimé — il était construit mais jamais utilisé.
# Le client ChromaDB prend directement host= et port=.

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

# Modèle d'embedding dédié — ATTENTION : doit être pullé séparément :
#   ollama pull nomic-embed-text
# Sans ça, _embed() échoue silencieusement et le RAG renvoie [] sans erreur visible.
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")

COLLECTION_NAME = "runbooks"

# FIX 3 : seuil de similarité cosinus abaissé de 1.5 à 0.8.
# En espace cosinus ChromaDB : 0 = identique, 2 = opposé.
# À 1.5, on retournait des docs à seulement 25% de similarité → bruit dans le prompt.
# À 0.8, on garde uniquement les docs à ~60%+ de similarité → contexte pertinent.
SIMILARITY_THRESHOLD = float(os.environ.get("RAG_SIMILARITY_THRESHOLD", "0.8"))

# Garde-fou : si ChromaDB n'est pas disponible, on ne réessaie pas à chaque appel.
_client = None
_client_unavailable = False


def _get_client():
    """Retourne le client ChromaDB (lazy init). Retourne None si indisponible."""
    global _client, _client_unavailable

    # Ne pas retenter si on sait déjà que ChromaDB est absent
    if _client_unavailable:
        return None

    if _client is not None:
        return _client

    try:
        import chromadb  # type: ignore

        _client = chromadb.HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)
        _client.heartbeat()  # vérifie la connexion au démarrage
        logger.info(
            "ChromaDB connected",
            extra={
                "event": "chromadb_connected",
                "host": CHROMADB_HOST,
                "port": CHROMADB_PORT,
            },
        )
        return _client

    except Exception as exc:
        _client_unavailable = True
        logger.warning(
            "ChromaDB not available — RAG disabled for this session",
            extra={
                "event": "chromadb_unavailable",
                "host": CHROMADB_HOST,
                "port": CHROMADB_PORT,
                "error": str(exc),
                "tip": f"Vérifie que ChromaDB tourne sur {CHROMADB_HOST}:{CHROMADB_PORT}",
            },
        )
        return None


async def _embed(text: str) -> Optional[list[float]]:
    """
    Génère un vecteur d'embedding via Ollama (modèle nomic-embed-text).

    Retourne None si Ollama est absent ou si le modèle n'est pas pullé.
    Pour activer : `ollama pull nomic-embed-text`
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
            )
            resp.raise_for_status()
            embedding = resp.json().get("embedding")

            if embedding is None:
                logger.warning(
                    "Ollama returned no embedding — modèle probablement absent",
                    extra={
                        "event": "embed_empty",
                        "model": EMBED_MODEL,
                        "tip": f"ollama pull {EMBED_MODEL}",
                    },
                )
            return embedding

    except httpx.ConnectError:
        logger.warning(
            "Ollama unreachable for embeddings",
            extra={"event": "embed_connect_error", "url": OLLAMA_BASE_URL},
        )
        return None
    except Exception as exc:
        logger.warning("Embedding failed", extra={"event": "embed_error", "error": str(exc)})
        return None


async def search_runbooks(query: str, n_results: int = 3) -> list[str]:
    """
    Retourne les n runbooks les plus pertinents pour un message de log donné.
    Retourne [] si ChromaDB ou Ollama embedding est indisponible.

    FIX 3 : seuls les résultats avec dist < SIMILARITY_THRESHOLD (0.8) sont retenus.
    """
    client = _get_client()
    if client is None:
        return []

    embedding = await _embed(query)
    if embedding is None:
        return []

    try:
        collection = client.get_collection(COLLECTION_NAME)
        results = collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=["documents", "distances"],
        )
        docs = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]

        # FIX 3 : filtrage strict par seuil de similarité
        relevant = [
            doc
            for doc, dist in zip(docs, distances)
            if dist < SIMILARITY_THRESHOLD
        ]

        if relevant:
            logger.info(
                "RAG: runbooks pertinents trouvés",
                extra={
                    "event": "rag_hit",
                    "n_relevant": len(relevant),
                    "n_candidates": len(docs),
                    "threshold": SIMILARITY_THRESHOLD,
                    "query_preview": query[:60],
                },
            )
        else:
            logger.debug(
                "RAG: aucun runbook suffisamment pertinent",
                extra={
                    "event": "rag_miss",
                    "n_candidates": len(docs),
                    "min_distance": min(distances) if distances else None,
                    "threshold": SIMILARITY_THRESHOLD,
                },
            )

        return relevant

    except Exception as exc:
        logger.warning(
            "ChromaDB query failed",
            extra={"event": "chromadb_query_error", "error": str(exc)},
        )
        return []


async def add_runbook(doc_id: str, category: str, content: str) -> bool:
    """
    Embed et stocke un document runbook dans ChromaDB.
    Retourne True si l'ingestion a réussi, False sinon.
    """
    client = _get_client()
    if client is None:
        return False

    embedding = await _embed(content)
    if embedding is None:
        return False

    try:
        try:
            collection = client.get_collection(COLLECTION_NAME)
        except Exception:
            collection = client.create_collection(
                COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )

        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{"category": category}],
        )
        logger.info(
            "Runbook ingested",
            extra={"event": "runbook_ingested", "doc_id": doc_id, "category": category},
        )
        return True

    except Exception as exc:
        logger.error(
            "Runbook ingestion failed",
            extra={"event": "runbook_ingest_error", "doc_id": doc_id, "error": str(exc)},
        )
        return False


async def ensure_collection() -> bool:
    """
    Crée la collection runbooks si elle n'existe pas encore.
    Retourne True si la collection est prête, False si ChromaDB est indisponible.
    """
    client = _get_client()
    if client is None:
        return False

    try:
        existing = [c.name for c in client.list_collections()]
        if COLLECTION_NAME not in existing:
            client.create_collection(
                COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                "ChromaDB collection created",
                extra={"event": "collection_created", "collection": COLLECTION_NAME},
            )
        return True

    except Exception as exc:
        logger.warning(
            "ChromaDB ensure_collection failed",
            extra={"event": "collection_ensure_error", "error": str(exc)},
        )
        return False