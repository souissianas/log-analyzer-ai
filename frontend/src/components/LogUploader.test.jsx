import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import LogUploader from "../components/LogUploader";
import { LanguageProvider } from "../i18n";

const wrap = (ui) => render(<LanguageProvider>{ui}</LanguageProvider>);

// ── Extension validation ───────────────────────────────────────────────────
describe("LogUploader — extension validation", () => {
  it("rejects unsupported file extensions", () => {
    const onAnalyze = vi.fn();
    wrap(<LogUploader onAnalyze={onAnalyze} disabled={false} />);

    const input = document.getElementById("log-file");
    fireEvent.change(input, {
      target: {
        files: [new File(["2026-06-18 ERROR fail"], "report.csv", { type: "text/csv" })],
      },
    });

    expect(screen.getByText(/Format non support/i)).toBeInTheDocument();
    expect(onAnalyze).not.toHaveBeenCalled();
  });

  it("accepts .log files and triggers analyze callback", () => {
    const onAnalyze = vi.fn();
    wrap(<LogUploader onAnalyze={onAnalyze} disabled={false} />);

    const input = document.getElementById("log-file");
    const file = new File(["2026-06-18 10:00:00 ERROR timeout"], "app.log", {
      type: "text/plain",
    });

    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /Analyser avec IA/i }));

    expect(onAnalyze).toHaveBeenCalledWith(file);
  });

  it("accepts .txt files", () => {
    const onAnalyze = vi.fn();
    wrap(<LogUploader onAnalyze={onAnalyze} disabled={false} />);

    const input = document.getElementById("log-file");
    const file = new File(["2026-06-18 ERROR fail"], "events.txt", { type: "text/plain" });
    fireEvent.change(input, { target: { files: [file] } });

    expect(screen.queryByText(/Format non support/i)).toBeNull();
  });
});

// ── Viewer role ────────────────────────────────────────────────────────────
describe("LogUploader — viewer role", () => {
  it("shows viewer restriction message for viewer role", () => {
    wrap(<LogUploader onAnalyze={vi.fn()} disabled={false} role="viewer" />);
    // The drop zone title should mention viewer restriction
    const input = document.getElementById("log-file");
    expect(input).toBeDisabled();
  });

  it("does not call onAnalyze when viewer tries to select file", () => {
    const onAnalyze = vi.fn();
    wrap(<LogUploader onAnalyze={onAnalyze} disabled={false} role="viewer" />);

    const input = document.getElementById("log-file");
    fireEvent.change(input, {
      target: {
        files: [new File(["log"], "app.log", { type: "text/plain" })],
      },
    });

    expect(onAnalyze).not.toHaveBeenCalled();
  });
});

// ── Disabled state ────────────────────────────────────────────────────────
describe("LogUploader — disabled state", () => {
  it("disables the file input when disabled=true", () => {
    wrap(<LogUploader onAnalyze={vi.fn()} disabled={true} />);
    const input = document.getElementById("log-file");
    expect(input).toBeDisabled();
  });

  it("does not call onAnalyze when disabled and form submitted", () => {
    const onAnalyze = vi.fn();
    wrap(<LogUploader onAnalyze={onAnalyze} disabled={true} />);
    // When disabled=true and no file, button shows uploaderBtnLoading = 'Analyse en cours...'
    const submitBtn = screen.getByRole("button", { name: /Analyse en cours|Analyser avec IA|Lecture seule/i });
    expect(submitBtn).toBeDisabled();
  });
});

// ── File removal ──────────────────────────────────────────────────────────
describe("LogUploader — file removal", () => {
  it("shows remove button after file selection", () => {
    wrap(<LogUploader onAnalyze={vi.fn()} disabled={false} />);
    const input = document.getElementById("log-file");
    const file = new File(["log"], "app.log", { type: "text/plain" });
    fireEvent.change(input, { target: { files: [file] } });

    // After selection, remove button should appear
    expect(screen.getByText(/Supprimer|Retirer/i)).toBeInTheDocument();
  });

  it("clears file when remove button is clicked", () => {
    wrap(<LogUploader onAnalyze={vi.fn()} disabled={false} />);
    const input = document.getElementById("log-file");
    const file = new File(["log"], "app.log", { type: "text/plain" });
    fireEvent.change(input, { target: { files: [file] } });

    // Click remove button
    fireEvent.click(screen.getByText(/Supprimer|Retirer/i));

    // File name should be gone
    expect(screen.queryByText("app.log")).toBeNull();
  });
});

// ── Drag and drop ─────────────────────────────────────────────────────────
describe("LogUploader — drag and drop", () => {
  it("does not crash on drop event with no files", () => {
    wrap(<LogUploader onAnalyze={vi.fn()} disabled={false} />);
    const label = document.querySelector("label.drop-zone");
    expect(() => {
      fireEvent.drop(label, {
        dataTransfer: { files: [] },
      });
    }).not.toThrow();
  });

  it("accepts dropped .log file", () => {
    const onAnalyze = vi.fn();
    wrap(<LogUploader onAnalyze={onAnalyze} disabled={false} />);
    const label = document.querySelector("label.drop-zone");
    const file = new File(["log content"], "dropped.log", { type: "text/plain" });

    fireEvent.drop(label, {
      dataTransfer: { files: [file] },
    });

    // File name should appear in drop zone
    expect(screen.getByText("dropped.log")).toBeInTheDocument();
  });

  it("does not accept drop when viewer", () => {
    const onAnalyze = vi.fn();
    wrap(<LogUploader onAnalyze={onAnalyze} disabled={false} role="viewer" />);
    const label = document.querySelector("label.drop-zone");
    const file = new File(["log"], "test.log", { type: "text/plain" });

    fireEvent.drop(label, { dataTransfer: { files: [file] } });

    // Should NOT show file name (viewer cannot drop)
    expect(screen.queryByText("test.log")).toBeNull();
  });
});
