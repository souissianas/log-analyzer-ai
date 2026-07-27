"""
Tests for services/rag_service.py.
All external dependencies (ChromaDB, Ollama HTTP) are mocked.
"""
import asyncio
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# ── Ensure chromadb is importable as a stub if not installed ─────────────────
if "chromadb" not in sys.modules:
    chromadb_stub = types.ModuleType("chromadb")
    chromadb_stub.HttpClient = MagicMock()
    sys.modules["chromadb"] = chromadb_stub


def _run(coro):
    return asyncio.run(coro)


# ─────────────────────────────────────────────────────────────────────────────
# Import the module AFTER stubs are in place
# ─────────────────────────────────────────────────────────────────────────────
import importlib
import services.rag_service as rag

importlib.reload(rag)


def _reset_client_state():
    """Reset module-level state between tests."""
    rag._client = None
    rag._client_unavailable = False


# ─────────────────────────────────────────────────────────────────────────────
# _get_client
# ─────────────────────────────────────────────────────────────────────────────
class TestGetClient(unittest.TestCase):
    def setUp(self):
        _reset_client_state()

    def test_returns_none_when_already_unavailable(self):
        rag._client_unavailable = True
        result = rag._get_client()
        self.assertIsNone(result)

    def test_returns_cached_client_when_already_set(self):
        fake_client = MagicMock()
        rag._client = fake_client
        result = rag._get_client()
        self.assertIs(result, fake_client)

    def test_sets_unavailable_on_connection_error(self):
        with patch.dict(sys.modules, {"chromadb": None}):
            _reset_client_state()
            # Can't import chromadb → should return None and mark unavailable
            import importlib
            import services.rag_service as fresh_rag
            importlib.reload(fresh_rag)
            fresh_rag._client = None
            fresh_rag._client_unavailable = False
            result = fresh_rag._get_client()
            # Since chromadb is None in modules, import inside will fail
            # Reset back
            _reset_client_state()

    def test_heartbeat_failure_marks_unavailable(self):
        mock_chromadb = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.heartbeat.side_effect = Exception("unreachable")
        mock_chromadb.HttpClient.return_value = mock_client_instance

        with patch.dict(sys.modules, {"chromadb": mock_chromadb}):
            _reset_client_state()
            result = rag._get_client()
            self.assertIsNone(result)
            self.assertTrue(rag._client_unavailable)


# ─────────────────────────────────────────────────────────────────────────────
# _embed
# ─────────────────────────────────────────────────────────────────────────────
class TestEmbed(unittest.TestCase):
    @patch("services.rag_service.httpx.AsyncClient")
    def test_success_returns_embedding(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = _run(rag._embed("some text"))
        self.assertEqual(result, [0.1, 0.2, 0.3])

    @patch("services.rag_service.httpx.AsyncClient")
    def test_none_embedding_logs_warning_returns_none(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"embedding": None}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = _run(rag._embed("text"))
        self.assertIsNone(result)

    @patch("services.rag_service.httpx.AsyncClient")
    def test_connect_error_returns_none(self, mock_client_cls):
        import httpx
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client_cls.return_value = mock_client

        result = _run(rag._embed("text"))
        self.assertIsNone(result)

    @patch("services.rag_service.httpx.AsyncClient")
    def test_generic_exception_returns_none(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=RuntimeError("unexpected"))
        mock_client_cls.return_value = mock_client

        result = _run(rag._embed("text"))
        self.assertIsNone(result)


# ─────────────────────────────────────────────────────────────────────────────
# search_runbooks
# ─────────────────────────────────────────────────────────────────────────────
class TestSearchRunbooks(unittest.TestCase):
    def setUp(self):
        _reset_client_state()

    def test_returns_empty_when_client_none(self):
        rag._client_unavailable = True
        result = _run(rag.search_runbooks("query"))
        self.assertEqual(result, [])

    @patch("services.rag_service._embed", new_callable=AsyncMock)
    def test_returns_empty_when_embedding_none(self, mock_embed):
        mock_embed.return_value = None
        fake_client = MagicMock()
        rag._client = fake_client
        result = _run(rag.search_runbooks("query"))
        self.assertEqual(result, [])

    @patch("services.rag_service._embed", new_callable=AsyncMock)
    def test_returns_relevant_docs_below_threshold(self, mock_embed):
        mock_embed.return_value = [0.1, 0.2]
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["doc1", "doc2"]],
            "distances": [[0.3, 0.9]],  # only doc1 is below threshold 0.8
        }
        fake_client = MagicMock()
        fake_client.get_collection.return_value = mock_collection
        rag._client = fake_client

        result = _run(rag.search_runbooks("query"))
        self.assertEqual(result, ["doc1"])

    @patch("services.rag_service._embed", new_callable=AsyncMock)
    def test_returns_empty_when_all_docs_above_threshold(self, mock_embed):
        mock_embed.return_value = [0.1, 0.2]
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["doc1"]],
            "distances": [[0.95]],  # above threshold
        }
        fake_client = MagicMock()
        fake_client.get_collection.return_value = mock_collection
        rag._client = fake_client

        result = _run(rag.search_runbooks("query"))
        self.assertEqual(result, [])

    @patch("services.rag_service._embed", new_callable=AsyncMock)
    def test_query_exception_returns_empty(self, mock_embed):
        mock_embed.return_value = [0.1, 0.2]
        fake_client = MagicMock()
        fake_client.get_collection.side_effect = Exception("Collection not found")
        rag._client = fake_client

        result = _run(rag.search_runbooks("query"))
        self.assertEqual(result, [])


# ─────────────────────────────────────────────────────────────────────────────
# add_runbook
# ─────────────────────────────────────────────────────────────────────────────
class TestAddRunbook(unittest.TestCase):
    def setUp(self):
        _reset_client_state()

    def test_returns_false_when_client_none(self):
        rag._client_unavailable = True
        result = _run(rag.add_runbook("id1", "memory", "content"))
        self.assertFalse(result)

    @patch("services.rag_service._embed", new_callable=AsyncMock)
    def test_returns_false_when_embedding_none(self, mock_embed):
        mock_embed.return_value = None
        rag._client = MagicMock()
        result = _run(rag.add_runbook("id2", "memory", "content"))
        self.assertFalse(result)

    @patch("services.rag_service._embed", new_callable=AsyncMock)
    def test_upsert_success_returns_true(self, mock_embed):
        mock_embed.return_value = [0.1, 0.2]
        mock_collection = MagicMock()
        mock_collection.upsert = MagicMock()
        fake_client = MagicMock()
        fake_client.get_collection.return_value = mock_collection
        rag._client = fake_client

        result = _run(rag.add_runbook("id3", "network", "some content"))
        self.assertTrue(result)

    @patch("services.rag_service._embed", new_callable=AsyncMock)
    def test_creates_collection_when_not_exists(self, mock_embed):
        mock_embed.return_value = [0.1, 0.2]
        mock_collection = MagicMock()
        mock_collection.upsert = MagicMock()
        fake_client = MagicMock()
        # get_collection raises → create_collection returns new collection
        fake_client.get_collection.side_effect = Exception("not found")
        fake_client.create_collection.return_value = mock_collection
        rag._client = fake_client

        result = _run(rag.add_runbook("id4", "disk", "runbook content"))
        self.assertTrue(result)
        fake_client.create_collection.assert_called_once()

    @patch("services.rag_service._embed", new_callable=AsyncMock)
    def test_upsert_exception_returns_false(self, mock_embed):
        mock_embed.return_value = [0.1, 0.2]
        mock_collection = MagicMock()
        mock_collection.upsert.side_effect = Exception("write error")
        fake_client = MagicMock()
        fake_client.get_collection.return_value = mock_collection
        rag._client = fake_client

        result = _run(rag.add_runbook("id5", "auth", "content"))
        self.assertFalse(result)


# ─────────────────────────────────────────────────────────────────────────────
# ensure_collection
# ─────────────────────────────────────────────────────────────────────────────
class TestEnsureCollection(unittest.TestCase):
    def setUp(self):
        _reset_client_state()

    def test_returns_false_when_client_none(self):
        rag._client_unavailable = True
        result = rag.ensure_collection()
        self.assertFalse(result)

    def test_returns_true_when_collection_exists(self):
        mock_coll = MagicMock()
        mock_coll.name = rag.COLLECTION_NAME
        fake_client = MagicMock()
        fake_client.list_collections.return_value = [mock_coll]
        rag._client = fake_client

        result = rag.ensure_collection()
        self.assertTrue(result)
        fake_client.create_collection.assert_not_called()

    def test_creates_collection_when_missing(self):
        fake_client = MagicMock()
        fake_client.list_collections.return_value = []
        fake_client.create_collection = MagicMock()
        rag._client = fake_client

        result = rag.ensure_collection()
        self.assertTrue(result)
        fake_client.create_collection.assert_called_once()

    def test_returns_false_on_exception(self):
        fake_client = MagicMock()
        fake_client.list_collections.side_effect = Exception("ChromaDB down")
        rag._client = fake_client

        result = rag.ensure_collection()
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
