"""
Tests for services/rag_service.py.
All external dependencies (ChromaDB, Ollama HTTP) are mocked.
"""
import asyncio
import sys
import types
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ── Ensure chromadb is importable as a stub if not installed ─────────────────
if "chromadb" not in sys.modules:
    chromadb_stub = types.ModuleType("chromadb")
    chromadb_stub.HttpClient = MagicMock()
    sys.modules["chromadb"] = chromadb_stub

import importlib
import services.rag_service as rag

importlib.reload(rag)


@pytest.fixture(autouse=True)
def reset_client_state(monkeypatch):
    """Reset module-level state between tests using monkeypatch."""
    monkeypatch.setattr(rag, "_client", None)
    monkeypatch.setattr(rag, "_client_unavailable", False)


# ─────────────────────────────────────────────────────────────────────────────
# _get_client
# ─────────────────────────────────────────────────────────────────────────────
def test_returns_none_when_already_unavailable(monkeypatch):
    monkeypatch.setattr(rag, "_client_unavailable", True)
    result = rag._get_client()
    assert result is None


def test_returns_cached_client_when_already_set(monkeypatch):
    fake_client = MagicMock()
    monkeypatch.setattr(rag, "_client", fake_client)
    result = rag._get_client()
    assert result is fake_client


def test_sets_unavailable_on_connection_error(monkeypatch):
    with patch.dict(sys.modules, {"chromadb": None}):
        fresh_rag = importlib.reload(rag)
        monkeypatch.setattr(fresh_rag, "_client", None)
        monkeypatch.setattr(fresh_rag, "_client_unavailable", False)
        result = fresh_rag._get_client()
        # Clean up reload
        importlib.reload(rag)


def test_heartbeat_failure_marks_unavailable(monkeypatch):
    mock_chromadb = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.heartbeat.side_effect = Exception("unreachable")
    mock_chromadb.HttpClient.return_value = mock_client_instance

    with patch.dict(sys.modules, {"chromadb": mock_chromadb}):
        result = rag._get_client()
        assert result is None
        assert rag._client_unavailable is True


# ─────────────────────────────────────────────────────────────────────────────
# _embed
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_embed_success_returns_embedding():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("services.rag_service.httpx.AsyncClient", return_value=mock_client):
        result = await rag._embed("some text")
        assert result == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_embed_none_embedding_logs_warning_returns_none():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"embedding": None}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("services.rag_service.httpx.AsyncClient", return_value=mock_client):
        result = await rag._embed("text")
        assert result is None


@pytest.mark.asyncio
async def test_embed_connect_error_returns_none():
    import httpx
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

    with patch("services.rag_service.httpx.AsyncClient", return_value=mock_client):
        result = await rag._embed("text")
        assert result is None


@pytest.mark.asyncio
async def test_embed_generic_exception_returns_none():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=RuntimeError("unexpected"))

    with patch("services.rag_service.httpx.AsyncClient", return_value=mock_client):
        result = await rag._embed("text")
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# search_runbooks
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_search_runbooks_returns_empty_when_client_none(monkeypatch):
    monkeypatch.setattr(rag, "_client_unavailable", True)
    result = await rag.search_runbooks("query")
    assert result == []


@pytest.mark.asyncio
async def test_search_runbooks_returns_empty_when_embedding_none(monkeypatch):
    fake_client = MagicMock()
    monkeypatch.setattr(rag, "_client", fake_client)
    with patch("services.rag_service._embed", new_callable=AsyncMock, return_value=None):
        result = await rag.search_runbooks("query")
        assert result == []


@pytest.mark.asyncio
async def test_search_runbooks_returns_relevant_docs_below_threshold(monkeypatch):
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["doc1", "doc2"]],
        "distances": [[0.3, 0.9]],  # only doc1 is below threshold 0.8
    }
    fake_client = MagicMock()
    fake_client.get_collection.return_value = mock_collection
    monkeypatch.setattr(rag, "_client", fake_client)

    with patch("services.rag_service._embed", new_callable=AsyncMock, return_value=[0.1, 0.2]):
        result = await rag.search_runbooks("query")
        assert result == ["doc1"]


@pytest.mark.asyncio
async def test_search_runbooks_returns_empty_when_all_docs_above_threshold(monkeypatch):
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["doc1"]],
        "distances": [[0.95]],  # above threshold
    }
    fake_client = MagicMock()
    fake_client.get_collection.return_value = mock_collection
    monkeypatch.setattr(rag, "_client", fake_client)

    with patch("services.rag_service._embed", new_callable=AsyncMock, return_value=[0.1, 0.2]):
        result = await rag.search_runbooks("query")
        assert result == []


@pytest.mark.asyncio
async def test_search_runbooks_query_exception_returns_empty(monkeypatch):
    fake_client = MagicMock()
    fake_client.get_collection.side_effect = Exception("Collection not found")
    monkeypatch.setattr(rag, "_client", fake_client)

    with patch("services.rag_service._embed", new_callable=AsyncMock, return_value=[0.1, 0.2]):
        result = await rag.search_runbooks("query")
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# add_runbook
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_add_runbook_returns_false_when_client_none(monkeypatch):
    monkeypatch.setattr(rag, "_client_unavailable", True)
    result = await rag.add_runbook("id1", "memory", "content")
    assert result is False


@pytest.mark.asyncio
async def test_add_runbook_returns_false_when_embedding_none(monkeypatch):
    monkeypatch.setattr(rag, "_client", MagicMock())
    with patch("services.rag_service._embed", new_callable=AsyncMock, return_value=None):
        result = await rag.add_runbook("id2", "memory", "content")
        assert result is False


@pytest.mark.asyncio
async def test_add_runbook_upsert_success_returns_true(monkeypatch):
    mock_collection = MagicMock()
    mock_collection.upsert = MagicMock()
    fake_client = MagicMock()
    fake_client.get_collection.return_value = mock_collection
    monkeypatch.setattr(rag, "_client", fake_client)

    with patch("services.rag_service._embed", new_callable=AsyncMock, return_value=[0.1, 0.2]):
        result = await rag.add_runbook("id3", "network", "some content")
        assert result is True


@pytest.mark.asyncio
async def test_add_runbook_creates_collection_when_not_exists(monkeypatch):
    mock_collection = MagicMock()
    mock_collection.upsert = MagicMock()
    fake_client = MagicMock()
    fake_client.get_collection.side_effect = Exception("not found")
    fake_client.create_collection.return_value = mock_collection
    monkeypatch.setattr(rag, "_client", fake_client)

    with patch("services.rag_service._embed", new_callable=AsyncMock, return_value=[0.1, 0.2]):
        result = await rag.add_runbook("id4", "disk", "runbook content")
        assert result is True
        fake_client.create_collection.assert_called_once()


@pytest.mark.asyncio
async def test_add_runbook_upsert_exception_returns_false(monkeypatch):
    mock_collection = MagicMock()
    mock_collection.upsert.side_effect = Exception("write error")
    fake_client = MagicMock()
    fake_client.get_collection.return_value = mock_collection
    monkeypatch.setattr(rag, "_client", fake_client)

    with patch("services.rag_service._embed", new_callable=AsyncMock, return_value=[0.1, 0.2]):
        result = await rag.add_runbook("id5", "auth", "content")
        assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# ensure_collection
# ─────────────────────────────────────────────────────────────────────────────
def test_ensure_collection_returns_false_when_client_none(monkeypatch):
    monkeypatch.setattr(rag, "_client_unavailable", True)
    result = rag.ensure_collection()
    assert result is False


def test_ensure_collection_returns_true_when_collection_exists(monkeypatch):
    mock_coll = MagicMock()
    mock_coll.name = rag.COLLECTION_NAME
    fake_client = MagicMock()
    fake_client.list_collections.return_value = [mock_coll]
    monkeypatch.setattr(rag, "_client", fake_client)

    result = rag.ensure_collection()
    assert result is True
    fake_client.create_collection.assert_not_called()


def test_ensure_collection_creates_collection_when_missing(monkeypatch):
    fake_client = MagicMock()
    fake_client.list_collections.return_value = []
    fake_client.create_collection = MagicMock()
    monkeypatch.setattr(rag, "_client", fake_client)

    result = rag.ensure_collection()
    assert result is True
    fake_client.create_collection.assert_called_once()


def test_ensure_collection_returns_false_on_exception(monkeypatch):
    fake_client = MagicMock()
    fake_client.list_collections.side_effect = Exception("ChromaDB down")
    monkeypatch.setattr(rag, "_client", fake_client)

    result = rag.ensure_collection()
    assert result is False
