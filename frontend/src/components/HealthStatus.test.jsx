import { render, screen, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../api", () => ({
  checkHealth: vi.fn(),
  checkReadiness: vi.fn(),
}));

import HealthStatus from "./HealthStatus";
import * as api from "../api";

// Note: NO fake timers — setInterval uses real timers but we never advance them,
// so only the initial poll() call matters for testing.

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("HealthStatus", () => {
  // ── Initial pill render ─────────────────────────────────────────────────
  it("renders Backend pill on initial mount", () => {
    api.checkHealth.mockResolvedValue({ status: "ok" });
    api.checkReadiness.mockResolvedValue({
      ok: true,
      database: { ok: true },
      ollama: { ollama_running: true, model_available: true, required_model: "llama3.2" },
    });
    render(<HealthStatus />);
    expect(screen.getByText(/Backend/i)).toBeInTheDocument();
  });

  // ── Backend OK ────────────────────────────────────────────────────────────
  it("shows Backend OK when health check succeeds", async () => {
    api.checkHealth.mockResolvedValue({ status: "ok" });
    api.checkReadiness.mockResolvedValue({
      ok: true,
      database: { ok: true },
      ollama: { ollama_running: true, model_available: true, required_model: "llama3.2" },
    });

    await act(async () => {
      render(<HealthStatus />);
    });

    expect(screen.getByText("Backend OK")).toBeInTheDocument();
  });

  // ── Backend KO ───────────────────────────────────────────────────────────
  it("shows Backend ... when health check fails", async () => {
    api.checkHealth.mockRejectedValue(new Error("unreachable"));
    api.checkReadiness.mockRejectedValue(new Error("unreachable"));

    await act(async () => {
      render(<HealthStatus />);
    });

    expect(screen.getByText(/Backend \.\.\./i)).toBeInTheDocument();
  });

  // ── Database OK ───────────────────────────────────────────────────────────
  it("shows DB OK when database is healthy", async () => {
    api.checkHealth.mockResolvedValue({ status: "ok" });
    api.checkReadiness.mockResolvedValue({
      ok: true,
      database: { ok: true },
      ollama: { ollama_running: false, model_available: false },
    });

    await act(async () => {
      render(<HealthStatus />);
    });

    expect(screen.getByText("DB OK")).toBeInTheDocument();
  });

  // ── Database KO ───────────────────────────────────────────────────────────
  it("shows DB ... when database is unhealthy", async () => {
    api.checkHealth.mockResolvedValue({ status: "ok" });
    api.checkReadiness.mockResolvedValue({
      ok: false,
      database: { ok: false },
      ollama: { ollama_running: false, model_available: false },
    });

    await act(async () => {
      render(<HealthStatus />);
    });

    expect(screen.getByText(/DB \.\.\./i)).toBeInTheDocument();
  });

  // ── Ollama OK ─────────────────────────────────────────────────────────────
  it("shows Ollama OK when running and model available", async () => {
    api.checkHealth.mockResolvedValue({ status: "ok" });
    api.checkReadiness.mockResolvedValue({
      ok: true,
      database: { ok: true },
      ollama: { ollama_running: true, model_available: true, required_model: "llama3.2" },
    });

    await act(async () => {
      render(<HealthStatus />);
    });

    expect(screen.getByText("Ollama OK")).toBeInTheDocument();
  });

  // ── Model name displayed ──────────────────────────────────────────────────
  it("shows model name when Ollama is available", async () => {
    api.checkHealth.mockResolvedValue({ status: "ok" });
    api.checkReadiness.mockResolvedValue({
      ok: true,
      database: { ok: true },
      ollama: { ollama_running: true, model_available: true, required_model: "llama3.2" },
    });

    await act(async () => {
      render(<HealthStatus />);
    });

    expect(screen.getByText("llama3.2")).toBeInTheDocument();
  });

  // ── Readiness error ───────────────────────────────────────────────────────
  it("handles readiness error gracefully without crashing", async () => {
    api.checkHealth.mockResolvedValue({ status: "ok" });
    api.checkReadiness.mockRejectedValue(new Error("network error"));

    await act(async () => {
      render(<HealthStatus />);
    });

    // Should not crash — DB pill should still be rendered
    expect(screen.getByText(/DB/i)).toBeInTheDocument();
  });
});
