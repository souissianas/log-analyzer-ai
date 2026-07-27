import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../api", () => ({
  checkHealth: vi.fn(),
  checkReadiness: vi.fn(),
}));

import HealthStatus from "./HealthStatus";
import * as api from "../api";

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("HealthStatus", () => {
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

  it.each([
    [
      "Backend OK",
      { status: "ok" },
      { ok: true, database: { ok: true }, ollama: { ollama_running: true, model_available: true, required_model: "llama3.2" } },
      "Backend OK"
    ],
    [
      "DB OK",
      { status: "ok" },
      { ok: true, database: { ok: true }, ollama: { ollama_running: false, model_available: false } },
      "DB OK"
    ],
    [
      "Ollama OK",
      { status: "ok" },
      { ok: true, database: { ok: true }, ollama: { ollama_running: true, model_available: true, required_model: "llama3.2" } },
      "Ollama OK"
    ]
  ])("shows %s when checks succeed", async (_, healthResp, readinessResp, expectedText) => {
    api.checkHealth.mockResolvedValue(healthResp);
    api.checkReadiness.mockResolvedValue(readinessResp);

    render(<HealthStatus />);

    expect(await screen.findByText(expectedText)).toBeInTheDocument();
  });

  it("shows Backend ... when health check fails", async () => {
    api.checkHealth.mockRejectedValue(new Error("unreachable"));
    api.checkReadiness.mockRejectedValue(new Error("unreachable"));

    render(<HealthStatus />);

    expect(await screen.findByText(/Backend \.\.\./i)).toBeInTheDocument();
  });

  it("shows DB ... when database is unhealthy", async () => {
    api.checkHealth.mockResolvedValue({ status: "ok" });
    api.checkReadiness.mockResolvedValue({
      ok: false,
      database: { ok: false },
      ollama: { ollama_running: false, model_available: false },
    });

    render(<HealthStatus />);

    expect(await screen.findByText(/DB \.\.\./i)).toBeInTheDocument();
  });

  it("shows model name when Ollama is available", async () => {
    api.checkHealth.mockResolvedValue({ status: "ok" });
    api.checkReadiness.mockResolvedValue({
      ok: true,
      database: { ok: true },
      ollama: { ollama_running: true, model_available: true, required_model: "llama3.2" },
    });

    render(<HealthStatus />);

    expect(await screen.findByText("llama3.2")).toBeInTheDocument();
  });

  it("handles readiness error gracefully without crashing", async () => {
    api.checkHealth.mockResolvedValue({ status: "ok" });
    api.checkReadiness.mockRejectedValue(new Error("network error"));

    render(<HealthStatus />);

    expect(await screen.findByText(/DB/i)).toBeInTheDocument();
  });
});
