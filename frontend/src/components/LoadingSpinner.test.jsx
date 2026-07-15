import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import LoadingSpinner from "./LoadingSpinner";

describe("LoadingSpinner", () => {
  // ── Sans progression ─────────────────────────────────────────────────────
  it("renders default message when no message prop", () => {
    render(<LoadingSpinner />);
    expect(screen.getByText(/Analyse en cours/i)).toBeInTheDocument();
  });

  it("renders custom message", () => {
    render(<LoadingSpinner message="Chargement des donnees..." />);
    expect(screen.getByText("Chargement des donnees...")).toBeInTheDocument();
  });

  it("renders fallback hint when no progress", () => {
    render(<LoadingSpinner />);
    // "L'inférence s'exécute sur le processeur local" — matcher sur mot sans accent
    expect(screen.getByText(/processeur local/i)).toBeInTheDocument();
  });

  it("does not render progress bar when no current/total", () => {
    const { container } = render(<LoadingSpinner />);
    expect(container.querySelector(".progress-container")).toBeNull();
  });

  it("does not render progress bar when total is 0", () => {
    const { container } = render(<LoadingSpinner current={0} total={0} />);
    expect(container.querySelector(".progress-container")).toBeNull();
  });

  // ── Avec progression ─────────────────────────────────────────────────────
  it("renders progress container when current and total provided", () => {
    const { container } = render(<LoadingSpinner current={3} total={10} />);
    expect(container.querySelector(".progress-container")).not.toBeNull();
  });

  it("renders correct progress label (3/10)", () => {
    render(<LoadingSpinner current={3} total={10} />);
    expect(screen.getByText(/3 \/ 10/i)).toBeInTheDocument();
  });

  it("renders percentage in progress label", () => {
    render(<LoadingSpinner current={5} total={10} />);
    // Plusieurs éléments peuvent afficher 50% (progress natif + label visible)
    expect(screen.getAllByText(/50%/i).length).toBeGreaterThanOrEqual(1);
  });

  it("renders remaining hint when progress active", () => {
    render(<LoadingSpinner current={2} total={8} />);
    // Hint includes "restants"
    expect(screen.getByText(/restants/i)).toBeInTheDocument();
  });

  it("renders progress bar filled to correct width", () => {
    const { container } = render(<LoadingSpinner current={1} total={4} />);
    const fill = container.querySelector(".progress-fill");
    expect(fill).not.toBeNull();
    expect(fill.style.width).toBe("25%");
  });

  it("renders native <progress> element for accessibility", () => {
    const { container } = render(<LoadingSpinner current={2} total={10} />);
    const progressEl = container.querySelector("progress");
    expect(progressEl).not.toBeNull();
    expect(progressEl.value).toBe(2);
    expect(progressEl.max).toBe(10);
  });

  it("renders spinner div", () => {
    const { container } = render(<LoadingSpinner />);
    expect(container.querySelector(".spinner")).not.toBeNull();
  });

  it("has aria-live polite attribute on overlay", () => {
    const { container } = render(<LoadingSpinner />);
    const overlay = container.querySelector(".loading-overlay");
    expect(overlay.getAttribute("aria-live")).toBe("polite");
  });
});
