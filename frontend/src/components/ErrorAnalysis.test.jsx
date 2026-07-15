import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ErrorAnalysis from "./ErrorAnalysis";
import { LanguageProvider } from "../i18n";

const wrap = (ui) => render(<LanguageProvider>{ui}</LanguageProvider>);

const makeError = (overrides = {}) => ({
  index: 1,
  line_number: 42,
  timestamp: "2026-06-18 10:00:00",
  level: "ERROR",
  message: "Connection timeout",
  category: "connection",
  success: true,
  analysis: {
    explanation: "Le service est injoignable.",
    causes: ["Reseau instable", "Serveur eteint"],
    solutions: ["Verifier le reseau", "Redemarrer le service"],
  },
  processing_time_seconds: 1.23,
  ...overrides,
});

// ── data = null ────────────────────────────────────────────────────────────
describe("ErrorAnalysis — data null", () => {
  it("renders nothing when data is null", () => {
    const { container } = wrap(<ErrorAnalysis data={null} />);
    expect(container.firstChild).toBeNull();
  });
});

// ── message only (no analyzed) ────────────────────────────────────────────
describe("ErrorAnalysis — message only", () => {
  it("renders message when no analyzed errors", () => {
    const data = { filename: "empty.log", message: "Aucune erreur detectee.", analyzed: [] };
    wrap(<ErrorAnalysis data={data} />);
    expect(screen.getByText(/Aucune erreur detectee/i)).toBeInTheDocument();
  });
});

// ── full render ────────────────────────────────────────────────────────────
describe("ErrorAnalysis — full render", () => {
  const baseData = {
    filename: "app.log",
    log_id: 7,
    total_errors_found: 3,
    total_analyzed: 2,
    skipped: 1,
    analyzed: [makeError()],
  };

  it("renders filename in title", () => {
    wrap(<ErrorAnalysis data={baseData} />);
    expect(screen.getByText(/app\.log/i)).toBeInTheDocument();
  });

  it("renders total errors found stat", () => {
    wrap(<ErrorAnalysis data={baseData} />);
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders error message", () => {
    wrap(<ErrorAnalysis data={baseData} />);
    expect(screen.getByText("Connection timeout")).toBeInTheDocument();
  });

  it("renders error level badge", () => {
    wrap(<ErrorAnalysis data={baseData} />);
    expect(screen.getByText("ERROR")).toBeInTheDocument();
  });

  it("renders analysis explanation", () => {
    wrap(<ErrorAnalysis data={baseData} />);
    expect(screen.getByText("Le service est injoignable.")).toBeInTheDocument();
  });

  it("renders causes list", () => {
    wrap(<ErrorAnalysis data={baseData} />);
    expect(screen.getByText("Reseau instable")).toBeInTheDocument();
    expect(screen.getByText("Serveur eteint")).toBeInTheDocument();
  });

  it("renders solutions list", () => {
    wrap(<ErrorAnalysis data={baseData} />);
    expect(screen.getByText("Verifier le reseau")).toBeInTheDocument();
  });

  it("renders timing info", () => {
    wrap(<ErrorAnalysis data={baseData} />);
    expect(screen.getByText(/1\.23s/i)).toBeInTheDocument();
  });

  it("renders category when not unknown", () => {
    wrap(<ErrorAnalysis data={baseData} />);
    expect(screen.getByText("connection")).toBeInTheDocument();
  });
});

// ── error levels & CSS classes ────────────────────────────────────────────
describe("ErrorAnalysis — level classes", () => {
  it("applies critical class for CRITICAL level", () => {
    const data = {
      filename: "f.log",
      analyzed: [makeError({ level: "CRITICAL" })],
    };
    const { container } = wrap(<ErrorAnalysis data={data} />);
    expect(container.querySelector(".level-critical")).not.toBeNull();
  });

  it("applies error class for ERROR level", () => {
    const data = { filename: "f.log", analyzed: [makeError({ level: "ERROR" })] };
    const { container } = wrap(<ErrorAnalysis data={data} />);
    expect(container.querySelector(".level-error")).not.toBeNull();
  });

  it("applies warning class for WARNING level", () => {
    const data = { filename: "f.log", analyzed: [makeError({ level: "WARNING" })] };
    const { container } = wrap(<ErrorAnalysis data={data} />);
    expect(container.querySelector(".level-warning")).not.toBeNull();
  });
});

// ── failed analysis ───────────────────────────────────────────────────────
describe("ErrorAnalysis — failed analysis", () => {
  it("renders failure message when success=false", () => {
    const data = {
      filename: "f.log",
      analyzed: [makeError({ success: false, error: "Ollama timeout", analysis: null })],
    };
    wrap(<ErrorAnalysis data={data} />);
    expect(screen.getByText(/Ollama timeout/i)).toBeInTheDocument();
  });
});

// ── export PDF button ─────────────────────────────────────────────────────
describe("ErrorAnalysis — export PDF button", () => {
  const dataWithLogId = {
    filename: "app.log",
    log_id: 7,
    analyzed: [makeError()],
  };

  it("shows export button for analyst with log_id", () => {
    const onExportPdf = vi.fn();
    wrap(<ErrorAnalysis data={dataWithLogId} onExportPdf={onExportPdf} role="analyst" />);
    const btn = screen.getByRole("button");
    expect(btn).toBeInTheDocument();
  });

  it("calls onExportPdf when export button is clicked", () => {
    const onExportPdf = vi.fn();
    wrap(<ErrorAnalysis data={dataWithLogId} onExportPdf={onExportPdf} role="analyst" />);
    fireEvent.click(screen.getByRole("button"));
    expect(onExportPdf).toHaveBeenCalledWith(7);
  });

  it("hides export button for viewer role", () => {
    const onExportPdf = vi.fn();
    wrap(<ErrorAnalysis data={dataWithLogId} onExportPdf={onExportPdf} role="viewer" />);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("hides export button when no log_id", () => {
    const dataNoId = { filename: "f.log", analyzed: [makeError()] };
    const onExportPdf = vi.fn();
    wrap(<ErrorAnalysis data={dataNoId} onExportPdf={onExportPdf} role="analyst" />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
