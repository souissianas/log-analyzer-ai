"""
Extra tests for services/ollama_service.py — covers branches not hit by existing tests.
All HTTP calls are mocked; no real Ollama required.
"""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from services.ollama_service import (
    MAX_LOG_LINE_CHARS,
    _first_present,
    _normalize_analysis,
    _normalize_list,
    _parse_json_if_possible,
    _strip_markdown_fence,
    _truncate_log_line,
    build_prompt,
    build_prompt_json,
    parse_ollama_response,
    parse_structured_analysis,
    _save_section,
    _is_structured_format,
    _build_payload,
    check_ollama_health,
    explain_logs,
    analyze_with_ollama,
    OLLAMA_MODEL,
)


def _run(coro):
    return asyncio.run(coro)


# ─────────────────────────────────────────────────────────────────────────────
# _is_structured_format
# ─────────────────────────────────────────────────────────────────────────────
class TestIsStructuredFormat(unittest.TestCase):
    def test_json_returns_true(self):
        self.assertTrue(_is_structured_format("json"))

    def test_structured_returns_true(self):
        self.assertTrue(_is_structured_format("structured"))

    def test_case_insensitive(self):
        self.assertTrue(_is_structured_format("JSON"))
        self.assertTrue(_is_structured_format("Structured"))

    def test_free_returns_false(self):
        self.assertFalse(_is_structured_format("free"))

    def test_empty_returns_false(self):
        self.assertFalse(_is_structured_format(""))

    def test_none_returns_false(self):
        self.assertFalse(_is_structured_format(None))


# ─────────────────────────────────────────────────────────────────────────────
# _strip_markdown_fence
# ─────────────────────────────────────────────────────────────────────────────
class TestStripMarkdownFence(unittest.TestCase):
    def test_no_fence_returns_value_unchanged(self):
        self.assertEqual(_strip_markdown_fence('{"a":1}'), '{"a":1}')

    def test_json_fence_stripped(self):
        val = "```json\n{\"a\":1}\n```"
        result = _strip_markdown_fence(val)
        self.assertEqual(result.strip(), '{"a":1}')

    def test_plain_fence_stripped(self):
        val = "```\n{\"a\":1}\n```"
        result = _strip_markdown_fence(val)
        self.assertIn("{", result)

    def test_fence_without_trailing_returns_unchanged(self):
        val = "```json\n{\"a\":1}"
        # No trailing ``` → returns as-is
        result = _strip_markdown_fence(val)
        self.assertTrue(result.startswith("```"))

    def test_only_json_language_tag_no_content(self):
        val = "```json```"
        result = _strip_markdown_fence(val)
        self.assertEqual(result, "")


# ─────────────────────────────────────────────────────────────────────────────
# _parse_json_if_possible
# ─────────────────────────────────────────────────────────────────────────────
class TestParseJsonIfPossible(unittest.TestCase):
    def test_valid_json_parsed(self):
        result = _parse_json_if_possible('{"key":"value"}')
        self.assertEqual(result, {"key": "value"})

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_json_if_possible(""))

    def test_non_string_returns_none(self):
        self.assertIsNone(_parse_json_if_possible(42))
        self.assertIsNone(_parse_json_if_possible(None))

    def test_invalid_json_returns_none(self):
        self.assertIsNone(_parse_json_if_possible("not json at all!!!"))

    def test_embedded_json_extracted(self):
        result = _parse_json_if_possible('some text {"explanation":"ok"} extra')
        self.assertEqual(result["explanation"], "ok")

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(_parse_json_if_possible("   "))


# ─────────────────────────────────────────────────────────────────────────────
# _first_present
# ─────────────────────────────────────────────────────────────────────────────
class TestFirstPresent(unittest.TestCase):
    def test_returns_first_matching_key(self):
        result = _first_present({"b": 2, "a": 1}, ("a", "b"))
        self.assertEqual(result, 1)

    def test_returns_none_when_no_key_matches(self):
        result = _first_present({"x": 9}, ("a", "b"))
        self.assertIsNone(result)

    def test_returns_second_key_when_first_absent(self):
        result = _first_present({"b": 2}, ("a", "b"))
        self.assertEqual(result, 2)


# ─────────────────────────────────────────────────────────────────────────────
# _normalize_list
# ─────────────────────────────────────────────────────────────────────────────
class TestNormalizeList(unittest.TestCase):
    def test_none_returns_empty(self):
        self.assertEqual(_normalize_list(None), [])

    def test_list_of_strings(self):
        result = _normalize_list(["a", "b", "c"])
        self.assertEqual(result, ["a", "b", "c"])

    def test_string_with_bullet_points(self):
        result = _normalize_list("- item one\n- item two")
        self.assertIn("item one", result)
        self.assertIn("item two", result)

    def test_json_string_list_parsed(self):
        result = _normalize_list('["x", "y"]')
        self.assertEqual(result, ["x", "y"])

    def test_non_string_non_list_wrapped(self):
        result = _normalize_list(42)
        self.assertEqual(result, ["42"])

    def test_empty_strings_filtered(self):
        result = _normalize_list(["valid", "", "  "])
        self.assertNotIn("", result)
        self.assertEqual(result, ["valid"])

    def test_asterisk_bullets_stripped(self):
        result = _normalize_list(["* item"])
        self.assertEqual(result, ["item"])


# ─────────────────────────────────────────────────────────────────────────────
# _truncate_log_line
# ─────────────────────────────────────────────────────────────────────────────
class TestTruncateLogLine(unittest.TestCase):
    def _fake_span(self):
        span = MagicMock()
        span.set_attribute = MagicMock()
        return span

    def test_short_line_unchanged(self):
        span = self._fake_span()
        result = _truncate_log_line("short line", span)
        self.assertEqual(result, "short line")

    def test_long_line_truncated(self):
        span = self._fake_span()
        long_line = "x" * (MAX_LOG_LINE_CHARS + 100)
        result = _truncate_log_line(long_line, span)
        self.assertEqual(len(result), MAX_LOG_LINE_CHARS)

    def test_span_attributes_set(self):
        span = self._fake_span()
        _truncate_log_line("hello", span)
        span.set_attribute.assert_any_call("log.original_length", 5)


# ─────────────────────────────────────────────────────────────────────────────
# _normalize_analysis
# ─────────────────────────────────────────────────────────────────────────────
class TestNormalizeAnalysis(unittest.TestCase):
    def test_basic_dict_normalized(self):
        result = _normalize_analysis({
            "explanation": "Something went wrong.",
            "causes": ["cause1"],
            "solutions": ["fix1"],
        })
        self.assertEqual(result["explanation"], "Something went wrong.")
        self.assertIsInstance(result["causes"], list)

    def test_nested_analysis_key_unwrapped(self):
        nested = {"analysis": {"explanation": "nested", "causes": [], "solutions": []}}
        result = _normalize_analysis(nested)
        self.assertEqual(result["explanation"], "nested")

    def test_max_depth_guard(self):
        # Three levels of nesting should hit the depth guard
        result = _normalize_analysis({"analysis": {"analysis": {"analysis": {"explanation": "deep"}}}})
        # Should not raise RecursionError; returns fallback
        self.assertIsInstance(result, dict)

    def test_non_dict_input_uses_text_parser(self):
        result = _normalize_analysis("raw text with **1. EXPLICATION** something")
        self.assertIsInstance(result, dict)

    def test_empty_dict_falls_back_to_text_parser(self):
        result = _normalize_analysis({})
        self.assertIsInstance(result, dict)

    def test_string_explanation_that_is_json_is_recursed(self):
        inner = json.dumps({"explanation": "inner explanation", "causes": [], "solutions": []})
        result = _normalize_analysis({"explanation": inner, "causes": [], "solutions": []})
        self.assertIn("explanation", result)

    def test_non_string_explanation_dumped(self):
        result = _normalize_analysis({"explanation": 42, "causes": [], "solutions": []})
        self.assertIn("42", result["explanation"])


# ─────────────────────────────────────────────────────────────────────────────
# parse_structured_analysis
# ─────────────────────────────────────────────────────────────────────────────
class TestParseStructuredAnalysis(unittest.TestCase):
    def test_valid_json_parsed(self):
        raw = '{"explanation":"ok","causes":["c1"],"solutions":["s1"]}'
        result = parse_structured_analysis(raw)
        self.assertEqual(result["explanation"], "ok")

    def test_non_json_falls_back_to_text(self):
        raw = "**1. EXPLICATION**\nSomething bad happened."
        result = parse_structured_analysis(raw)
        self.assertIsInstance(result, dict)


# ─────────────────────────────────────────────────────────────────────────────
# parse_ollama_response
# ─────────────────────────────────────────────────────────────────────────────
class TestParseOllamaResponse(unittest.TestCase):
    def test_empty_string_returns_empty(self):
        result = parse_ollama_response("")
        self.assertEqual(result["explanation"], "")
        self.assertEqual(result["causes"], [])

    def test_full_sections_parsed(self):
        raw = (
            "**1. EXPLICATION**\nServer unreachable.\n"
            "**2. CAUSES POSSIBLES**\n- Network issue\n- Firewall\n"
            "**3. SOLUTIONS RECOMMANDEES**\n- Check network\n- Restart"
        )
        result = parse_ollama_response(raw)
        self.assertIn("Server unreachable", result["explanation"])
        self.assertGreater(len(result["causes"]), 0)
        self.assertGreater(len(result["solutions"]), 0)

    def test_no_sections_puts_all_in_explanation(self):
        raw = "Some random text without sections."
        result = parse_ollama_response(raw)
        self.assertIn("random text", result["explanation"])


# ─────────────────────────────────────────────────────────────────────────────
# _save_section
# ─────────────────────────────────────────────────────────────────────────────
class TestSaveSection(unittest.TestCase):
    def test_no_section_does_nothing(self):
        result = {"explanation": "", "causes": [], "solutions": []}
        _save_section(result, None, ["text"])
        self.assertEqual(result["explanation"], "")

    def test_empty_content_does_nothing(self):
        result = {"explanation": "", "causes": [], "solutions": []}
        _save_section(result, "explanation", [])
        self.assertEqual(result["explanation"], "")

    def test_explanation_joined(self):
        result = {"explanation": "", "causes": [], "solutions": []}
        _save_section(result, "explanation", ["word1", "word2"])
        self.assertEqual(result["explanation"], "word1 word2")

    def test_causes_normalized(self):
        result = {"explanation": "", "causes": [], "solutions": []}
        _save_section(result, "causes", ["- item1", "- item2"])
        self.assertIsInstance(result["causes"], list)

    def test_solutions_normalized(self):
        result = {"explanation": "", "causes": [], "solutions": []}
        _save_section(result, "solutions", ["fix it"])
        self.assertIsInstance(result["solutions"], list)


# ─────────────────────────────────────────────────────────────────────────────
# _build_payload
# ─────────────────────────────────────────────────────────────────────────────
class TestBuildPayload(unittest.TestCase):
    def test_structured_adds_format_json(self):
        payload = _build_payload("prompt text", structured=True)
        self.assertEqual(payload["format"], "json")

    def test_non_structured_no_format_key(self):
        payload = _build_payload("prompt text", structured=False)
        self.assertNotIn("format", payload)

    def test_payload_has_model_and_stream(self):
        payload = _build_payload("p", structured=False)
        self.assertEqual(payload["model"], OLLAMA_MODEL)
        self.assertFalse(payload["stream"])


# ─────────────────────────────────────────────────────────────────────────────
# build_prompt / build_prompt_json
# ─────────────────────────────────────────────────────────────────────────────
class TestBuildPrompts(unittest.TestCase):
    def test_build_prompt_contains_log_line(self):
        result = build_prompt("Connection timeout", "ERROR")
        self.assertIn("Connection timeout", result)

    def test_build_prompt_json_contains_log_line(self):
        result = build_prompt_json("disk full", "CRITICAL")
        self.assertIn("disk full", result)

    def test_build_prompt_json_with_context_docs(self):
        result = build_prompt_json("err", "ERROR", context_docs=["Runbook A content"])
        self.assertIn("Runbook A content", result)

    def test_build_prompt_json_no_context_docs(self):
        result = build_prompt_json("err", "ERROR", context_docs=None)
        self.assertNotIn("Runbooks internes", result)


# ─────────────────────────────────────────────────────────────────────────────
# explain_logs — mocked HTTP
# ─────────────────────────────────────────────────────────────────────────────
class TestExplainLogs(unittest.TestCase):
    def test_empty_input_returns_no_errors(self):
        result = _run(explain_logs(""))
        self.assertIn("Aucune erreur", result)

    def test_whitespace_only_returns_no_errors(self):
        result = _run(explain_logs("   "))
        self.assertIn("Aucune erreur", result)

    @patch("services.ollama_service.httpx.AsyncClient")
    def test_connect_error_returns_message(self, mock_client_cls):
        import httpx
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = httpx.ConnectError("refused")
        mock_client_cls.return_value = mock_client
        result = _run(explain_logs("some errors here"))
        self.assertIn("Ollama non disponible", result)

    @patch("services.ollama_service.httpx.AsyncClient")
    def test_timeout_returns_message(self, mock_client_cls):
        import httpx
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        mock_client_cls.return_value = mock_client
        result = _run(explain_logs("some errors here"))
        self.assertIn("timeout", result.lower())

    @patch("services.ollama_service.httpx.AsyncClient")
    def test_generic_error_returns_message(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = RuntimeError("unexpected")
        mock_client_cls.return_value = mock_client
        result = _run(explain_logs("some errors here"))
        self.assertIn("Impossible de generer", result)

    @patch("services.ollama_service.httpx.AsyncClient")
    def test_success_returns_response(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "Global analysis here"}
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client
        result = _run(explain_logs("ERROR Connection failed"))
        self.assertEqual(result, "Global analysis here")


# ─────────────────────────────────────────────────────────────────────────────
# check_ollama_health — mocked HTTP
# ─────────────────────────────────────────────────────────────────────────────
class TestCheckOllamaHealth(unittest.TestCase):
    @patch("services.ollama_service.httpx.AsyncClient")
    def test_success_running(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"models": [{"name": OLLAMA_MODEL}]}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = _run(check_ollama_health())
        self.assertTrue(result["ollama_running"])
        self.assertTrue(result["model_available"])

    @patch("services.ollama_service.httpx.AsyncClient")
    def test_connection_error(self, mock_client_cls):
        import httpx
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client_cls.return_value = mock_client

        result = _run(check_ollama_health())
        self.assertFalse(result["ollama_running"])
        self.assertIn("error", result)


# ─────────────────────────────────────────────────────────────────────────────
# analyze_with_ollama — mocked HTTP
# ─────────────────────────────────────────────────────────────────────────────
class TestAnalyzeWithOllama(unittest.TestCase):
    @patch("services.ollama_service.httpx.AsyncClient")
    def test_structured_success(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"response": '{"explanation":"ok","causes":[],"solutions":[]}'}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = _run(analyze_with_ollama("disk full", "ERROR", output_format="structured", use_rag=False))
        self.assertTrue(result["success"])
        self.assertIsNone(result["error"])

    @patch("services.ollama_service.httpx.AsyncClient")
    def test_connect_error_returns_failure(self, mock_client_cls):
        import httpx
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client_cls.return_value = mock_client

        result = _run(analyze_with_ollama("err", "ERROR", use_rag=False))
        self.assertFalse(result["success"])
        self.assertIn("Ollama non disponible", result["error"])

    @patch("services.ollama_service.httpx.AsyncClient")
    def test_timeout_returns_failure(self, mock_client_cls):
        import httpx
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client_cls.return_value = mock_client

        result = _run(analyze_with_ollama("err", "ERROR", use_rag=False))
        self.assertFalse(result["success"])
        self.assertIn("timeout", result["error"].lower())

    @patch("services.ollama_service.httpx.AsyncClient")
    def test_http_status_error_returns_failure(self, mock_client_cls):
        import httpx
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=mock_response)
        )
        mock_client_cls.return_value = mock_client

        result = _run(analyze_with_ollama("err", "ERROR", use_rag=False))
        self.assertFalse(result["success"])

    @patch("services.ollama_service.httpx.AsyncClient")
    def test_free_format_uses_text_parser(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "response": "**1. EXPLICATION**\nServer is down.\n**2. CAUSES POSSIBLES**\n- Network\n**3. SOLUTIONS RECOMMANDEES**\n- Restart"
        }
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = _run(analyze_with_ollama("Server down", "ERROR", output_format="free", use_rag=False))
        self.assertTrue(result["success"])
        self.assertIn("explanation", result["analysis"])


if __name__ == "__main__":
    unittest.main()
