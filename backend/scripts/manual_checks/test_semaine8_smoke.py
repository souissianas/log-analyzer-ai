#!/usr/bin/env python3
"""Smoke tests for Semaine 8 final validation.

These tests target a running backend at BACKEND_URL.
They validate the end-to-end API contract used by the React interface.
"""

import os
import sys
import time
from pathlib import Path

import httpx


BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    sys.exit(1)


def assert_response_ok(response: httpx.Response, label: str) -> dict:
    if response.status_code != 200:
        fail(f"{label}: HTTP {response.status_code} - {response.text}")
    return response.json()


def main() -> None:
    print("Semaine 8 - smoke tests")
    print(f"Backend cible: {BACKEND_URL}")

    with httpx.Client(timeout=180.0) as client:
        health = assert_response_ok(client.get(f"{BACKEND_URL}/health"), "Backend health")
        if health.get("status") != "ok":
            fail(f"Backend health inattendu: {health}")
        ok("Backend FastAPI disponible")

        ollama = assert_response_ok(client.get(f"{BACKEND_URL}/ollama/health"), "Ollama health")
        if not ollama.get("ollama_running") or not ollama.get("model_available"):
            fail(f"Ollama ou modele indisponible: {ollama}")
        ok(f"Ollama disponible avec {ollama.get('required_model')}")

        # Authenticate via register & login to obtain JWT token
        try:
            client.post(
                f"{BACKEND_URL}/auth/register",
                json={
                    "email": "smoke_test_analyst@example.com",
                    "password": "Password123",
                    "tenant_name": "Smoke Test Tenant",
                    "tenant_slug": "smoke-test-tenant",
                    "role": "analyst",
                },
            )
        except Exception:
            pass

        login_resp = client.post(
            f"{BACKEND_URL}/auth/login",
            json={
                "email": "smoke_test_analyst@example.com",
                "password": "Password123",
            },
        )
        if login_resp.status_code != 200:
            fail(f"Login failed: HTTP {login_resp.status_code} - {login_resp.text}")
        
        token = login_resp.json().get("access_token")
        if not token:
            fail("Login response did not contain access_token")
        ok("Authentification réussie")

        headers = {"Authorization": f"Bearer {token}"}

        sample = Path("test_semaine8_smoke.log")
        sample.write_text(
            "\n".join(
                [
                    "2026-06-18 10:00:00 INFO Application started",
                    "2026-06-18 10:01:00 ERROR Database timeout after 30 seconds",
                    "2026-06-18 10:02:00 WARNING Disk usage above threshold",
                ]
            ),
            encoding="utf-8",
        )

        started = time.time()
        with sample.open("rb") as handle:
            response = client.post(
                f"{BACKEND_URL}/ollama/analyze-file",
                params={"max_errors": 2, "output_format": "structured"},
                files={"file": (sample.name, handle, "text/plain")},
                headers=headers,
            )

        payload = assert_response_ok(response, "Analyze file")
        ok(f"Upload analyse en {time.time() - started:.1f}s")

        if payload.get("total_errors_found", 0) < 2:
            fail(f"Nombre d'erreurs detectees inattendu: {payload}")
        if payload.get("total_analyzed") != 2:
            fail(f"Nombre d'erreurs analysees inattendu: {payload}")
        if not payload.get("log_id"):
            fail("Analyse non sauvegardee: log_id manquant")

        for item in payload.get("analyzed", []):
            analysis = item.get("analysis") or {}
            if not item.get("success"):
                fail(f"Analyse IA echouee pour l'erreur #{item.get('index')}: {item.get('error')}")
            if not isinstance(analysis.get("explanation"), str) or not analysis["explanation"]:
                fail(f"Explication manquante: {item}")
            if not isinstance(analysis.get("causes"), list) or not analysis["causes"]:
                fail(f"Causes manquantes: {item}")
            if not isinstance(analysis.get("solutions"), list) or not analysis["solutions"]:
                fail(f"Solutions manquantes: {item}")
        ok("Contrat IA valide: explanation, causes, solutions")

        history = assert_response_ok(client.get(f"{BACKEND_URL}/logs", headers=headers), "Logs history")
        if history.get("count", 0) < 1:
            fail(f"Historique vide apres sauvegarde: {history}")
        ok("Historique des analyses disponible")

    print("Semaine 8 validee cote API")


if __name__ == "__main__":
    main()
