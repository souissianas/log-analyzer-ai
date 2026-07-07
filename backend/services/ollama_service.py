# backend/services/ollama_service.py

import json
import logging
import os
import re
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

from core.telemetry import get_tracer
from core.metrics import OLLAMA_REQUEST_DURATION
tracer = get_tracer("ollama-service")

try:
    from opentelemetry.trace import StatusCode
except ImportError:
    class StatusCode:
        OK = 1
        ERROR = 2

# Import RAG — optional, fails gracefully
try:
    from services.rag_service import search_runbooks as _search_runbooks
    _RAG_AVAILABLE = True
except ImportError:
    _RAG_AVAILABLE = False
    async def _search_runbooks(*_, **__):  # type: ignore
        return []

# Local development uses Ollama on localhost. Docker overrides this value.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
OLLAMA_KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "5m")
OLLAMA_TIMEOUT = 90.0

STRUCTURED_FORMATS = {"json", "structured"}

# Max characters kept from a single log line before sending it to Ollama.
# Some Java stack traces exceed 5000 chars; without this cap they silently
# overflow num_ctx (1536) and Ollama truncates them without warning.
MAX_LOG_LINE_CHARS = 2000

# Max recursion depth for _normalize_analysis() when Ollama returns
# pathologically nested JSON (e.g. {"analysis": {"analysis": {...}}}).
MAX_NORMALIZE_DEPTH = 3


def build_prompt(log_line: str, error_level: str) -> str:
    """Builds a human-readable prompt for free-text output."""
    return f"""Tu es un expert en analyse de logs et en debogage de systemes informatiques.

Analyse cette ligne de log de type {error_level} et reponds en francais avec exactement ces 3 sections :

**1. EXPLICATION**
Explique clairement ce que signifie cette erreur en langage simple (2-3 phrases maximum).

**2. CAUSES POSSIBLES**
Liste 2 a 4 causes probables sous forme de points (commence chaque point par "- ").

**3. SOLUTIONS RECOMMANDEES**
Propose 2 a 4 actions concretes a effectuer sous forme de points (commence chaque point par "- ").

Ligne de log a analyser :
{log_line}

Reponds uniquement avec les 3 sections demandees, sans introduction ni conclusion."""


def build_prompt_json(log_line: str, error_level: str, context_docs: list[str] | None = None) -> str:
    """Builds the strict structured-output prompt, optionally enriched with RAG runbook context."""
    rag_section = ""
    if context_docs:
        joined = "\n---\n".join(context_docs[:2])  # max 2 snippets to save tokens
        rag_section = f"\nRunbooks internes:\n{joined}\n"

    return f"""Expert logs. Retourne uniquement un JSON valide, sans Markdown.
Schema:
{{"explanation":"2-3 phrases fr","causes":["cause1","cause2"],"solutions":["action1","action2"]}}
Regles: cles exactes, tableaux de strings, pas de JSON imbrique.
{rag_section}
Niveau: {error_level}
Log: {log_line}
"""


def _is_structured_format(output_format: str) -> bool:
    return bool(output_format and output_format.lower() in STRUCTURED_FORMATS)


async def analyze_with_ollama(
    log_line: str,
    error_level: str,
    output_format: str = "structured",
    use_rag: bool = True,
) -> dict:
    """
    Sends one log line to Ollama and returns:
    {success, analysis, raw_response, error, rag_used}
    """
    with tracer.start_as_current_span("analyze_with_ollama") as span:
        span.set_attribute("log.level", error_level)
        span.set_attribute("ollama.model", OLLAMA_MODEL)

        # Truncate abnormally long lines (e.g. Java stack traces) so they
        # don't silently overflow Ollama's num_ctx window.
        original_len = len(log_line)
        if original_len > MAX_LOG_LINE_CHARS:
            log_line = log_line[:MAX_LOG_LINE_CHARS]
            logger.warning(
                "log_line truncated before Ollama call",
                extra={"original_length": original_len, "truncated_to": MAX_LOG_LINE_CHARS},
            )
        span.set_attribute("log.original_length", original_len)
        span.set_attribute("log.truncated", original_len > MAX_LOG_LINE_CHARS)

        structured = _is_structured_format(output_format)

        # RAG context retrieval
        context_docs: list[str] = []
        if structured and use_rag and _RAG_AVAILABLE:
            try:
                context_docs = await _search_runbooks(log_line, n_results=3)
                if context_docs:
                    logger.info(
                        "RAG context retrieved",
                        extra={"n_docs": len(context_docs), "query": log_line[:60]},
                    )
            except Exception as rag_exc:
                logger.warning("RAG search failed", extra={"error": str(rag_exc)})

        prompt = build_prompt_json(log_line, error_level, context_docs=context_docs) if structured else build_prompt(log_line, error_level)
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
                "num_ctx": 1536,
                "num_predict": 200,
            },
        }
        if structured:
            # Ollama supports JSON mode for models that can follow structured output.
            payload["format"] = "json"

        try:
            start_time = time.perf_counter()
            async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
                logger.info("Sending to Ollama: %s -> %s...", error_level, log_line[:60])
                response = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
                response.raise_for_status()
            
            duration = time.perf_counter() - start_time
            OLLAMA_REQUEST_DURATION.observe(duration)

            raw_text = response.json().get("response", "")
            logger.info("Ollama response received")

            analysis = parse_structured_analysis(raw_text) if structured else parse_ollama_response(raw_text)

            span.set_attribute("rag.used", len(context_docs) > 0)
            span.set_attribute("rag.docs_count", len(context_docs))
            span.set_status(StatusCode.OK)

            return {
                "success": True,
                "analysis": analysis,
                "raw_response": raw_text,
                "error": None,
                "rag_used": len(context_docs) > 0,
                "rag_docs_count": len(context_docs),
            }

        except httpx.ConnectError as e:
            msg = "Ollama non disponible. Lance : ollama serve"
            logger.error(msg)
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, msg)
            return {"success": False, "analysis": None, "raw_response": None, "error": msg}

        except httpx.TimeoutException as e:
            msg = f"Ollama timeout ({OLLAMA_TIMEOUT}s depasse)"
            logger.error(msg)
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, msg)
            return {"success": False, "analysis": None, "raw_response": None, "error": msg}

        except httpx.HTTPStatusError as e:
            msg = f"Erreur HTTP {e.response.status_code} : {e.response.text}"
            logger.error(msg)
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, msg)
            return {"success": False, "analysis": None, "raw_response": None, "error": msg}

        except Exception as e:
            msg = f"Erreur inattendue : {str(e)}"
            logger.exception(msg)
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, msg)
            return {"success": False, "analysis": None, "raw_response": None, "error": msg}


def _strip_markdown_fence(value: str) -> str:
    value = value.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", value, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else value


def _parse_json_if_possible(value: str):
    if not isinstance(value, str):
        return None

    value = _strip_markdown_fence(value)
    if not value:
        return None

    try:
        return json.loads(value)
    except Exception:
        start = value.find("{")
        end = value.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(value[start : end + 1])
            except Exception:
                return None
    return None


def _first_present(parsed: dict, keys: tuple[str, ...]):
    for key in keys:
        if key in parsed:
            return parsed[key]
    return None


def _normalize_list(value) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        parsed = _parse_json_if_possible(value)
        if isinstance(parsed, list):
            items = parsed
        else:
            items = re.split(r"\n+|(?:^|\s)[-*]\s+", value)
    else:
        items = [value]

    normalized = []
    for item in items:
        text = str(item).strip().lstrip("-*• ").strip()
        if text:
            normalized.append(text)
    return normalized


def parse_structured_analysis(raw_text: str) -> dict:
    """Parses the structured answer expected from Ollama JSON mode."""
    parsed = _parse_json_if_possible(raw_text)
    if isinstance(parsed, dict):
        return _normalize_analysis(parsed)
    return parse_ollama_response(raw_text)


def _normalize_analysis(parsed: object, _depth: int = 0) -> dict:
    """Normalizes model JSON into the API contract used by the frontend.

    `_depth` guards against pathologically nested JSON returned by Ollama
    (e.g. {"analysis": {"analysis": {"analysis": ...}}}), which would
    otherwise cause unbounded recursion / a RecursionError.
    """
    analysis = {"explanation": "", "causes": [], "solutions": []}

    if _depth >= MAX_NORMALIZE_DEPTH:
        logger.warning("Max normalize depth reached, falling back to raw text parsing")
        return parse_ollama_response(json.dumps(parsed, ensure_ascii=False) if not isinstance(parsed, str) else parsed)

    if isinstance(parsed, str):
        parsed_json = _parse_json_if_possible(parsed)
        if isinstance(parsed_json, dict):
            parsed = parsed_json
        else:
            return parse_ollama_response(parsed)

    if not isinstance(parsed, dict):
        return parse_ollama_response(str(parsed))

    nested = _first_present(parsed, ("analysis", "analyse", "result", "response"))
    if isinstance(nested, dict):
        return _normalize_analysis(nested, _depth=_depth + 1)

    explanation = _first_present(parsed, ("explanation", "explication", "description", "summary"))
    if isinstance(explanation, str):
        nested_explanation = _parse_json_if_possible(explanation)
        if isinstance(nested_explanation, dict):
            return _normalize_analysis(nested_explanation, _depth=_depth + 1)
        analysis["explanation"] = explanation.strip()
    elif explanation:
        analysis["explanation"] = json.dumps(explanation, ensure_ascii=False)

    causes = _first_present(parsed, ("causes", "causes_possibles", "possible_causes"))
    solutions = _first_present(
        parsed,
        ("solutions", "solutions_recommandees", "recommended_solutions", "actions"),
    )
    analysis["causes"] = _normalize_list(causes)
    analysis["solutions"] = _normalize_list(solutions)

    if not any([analysis["explanation"], analysis["causes"], analysis["solutions"]]):
        return parse_ollama_response(str(parsed))

    return analysis


async def explain_logs(errors_text: str) -> str:
    """
    Generates a global free-text explanation for a block of extracted log errors.
    Used by the legacy /analyze endpoint.
    """
    if not errors_text or not errors_text.strip():
        return "Aucune erreur detectee"

    prompt = f"""Tu es un expert en analyse de logs et en debogage de systemes informatiques.

Voici un ensemble de lignes d'erreur extraites d'un fichier de log :

{errors_text}

Donne une explication globale concise (4-6 phrases) de ce qui semble se passer dans ce systeme,
les causes probables communes, et les premieres pistes de resolution a explorer.
Reponds en francais, sans introduction ni conclusion superflue."""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "top_p": 0.9},
    }

    try:
        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            response = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
            response.raise_for_status()
        duration = time.perf_counter() - start_time
        OLLAMA_REQUEST_DURATION.observe(duration)
        return response.json().get("response", "").strip()

    except httpx.ConnectError:
        return "Ollama non disponible. Lance : ollama serve"
    except httpx.TimeoutException:
        return f"Ollama timeout ({OLLAMA_TIMEOUT}s depasse)"
    except Exception as e:
        logger.exception("Erreur dans explain_logs")
        return f"Impossible de generer une explication IA : {str(e)}"


def parse_ollama_response(raw_text: str) -> dict:
    """
    Extracts the 3 sections from a free-text Llama answer.
    Returns: {explanation, causes, solutions}
    """
    result = {"explanation": "", "causes": [], "solutions": []}
    if not raw_text:
        return result

    current_section: Optional[str] = None
    current_content = []

    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        header = line.upper().strip("*# :")
        if "EXPLICATION" in header:
            _save_section(result, current_section, current_content)
            current_section, current_content = "explanation", []
        elif "CAUSES" in header:
            _save_section(result, current_section, current_content)
            current_section, current_content = "causes", []
        elif "SOLUTIONS" in header:
            _save_section(result, current_section, current_content)
            current_section, current_content = "solutions", []
        elif current_section:
            current_content.append(line)

    _save_section(result, current_section, current_content)

    if not any([result["explanation"], result["causes"], result["solutions"]]):
        result["explanation"] = raw_text.strip()

    return result


def _save_section(result: dict, section: Optional[str], content: list) -> None:
    if not section or not content:
        return
    if section == "explanation":
        result["explanation"] = " ".join(content).strip()
    else:
        result[section] = _normalize_list(content)


async def check_ollama_health() -> dict:
    """Checks that Ollama is running and that the expected model is available."""
    with tracer.start_as_current_span("check_ollama_health") as span:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                response.raise_for_status()
                models = [m["name"] for m in response.json().get("models", [])]
                model_avail = any(OLLAMA_MODEL in m for m in models)
                span.set_attribute("ollama.running", True)
                span.set_attribute("ollama.model_available", model_avail)
                span.set_status(StatusCode.OK)
                return {
                    "ollama_running": True,
                    "model_available": model_avail,
                    "available_models": models,
                    "required_model": OLLAMA_MODEL,
                }
        except Exception as e:
            span.record_exception(e)
            span.set_attribute("ollama.running", False)
            span.set_status(StatusCode.ERROR, str(e))
            return {
                "ollama_running": False,
                "model_available": False,
                "available_models": [],
                "required_model": OLLAMA_MODEL,
                "error": str(e),
            }