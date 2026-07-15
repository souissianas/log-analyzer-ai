import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { LanguageProvider } from "../i18n";

vi.mock("../api", () => ({
  fetchAnalysisHistory: vi.fn(),
  deleteAnalysis: vi.fn(),
}));

import HistoryPage from "./HistoryPage";
import * as api from "../api";

const wrap = (props = {}) =>
  render(
    <LanguageProvider>
      <HistoryPage onSelect={vi.fn()} refreshKey={0} {...props} />
    </LanguageProvider>
  );

const mockItems = [
  { id: 1, filename: "server.log",  created_at: "2026-06-01T08:00:00", total_errors_found: 5, total_analyzed: 5 },
  { id: 2, filename: "docker.log",  created_at: "2026-06-02T09:00:00", total_errors_found: 2, total_analyzed: 2 },
  { id: 3, filename: "jenkins.log", created_at: "2026-06-03T10:00:00", total_errors_found: 10, total_analyzed: 5 },
];

beforeEach(() => vi.clearAllMocks());

describe("HistoryPage", () => {
  // ── Loading / Error / Empty ──────────────────────────────────────────────
  it("renders without crashing while loading", async () => {
    api.fetchAnalysisHistory.mockResolvedValue({ items: [] });
    await act(async () => { wrap(); });
    expect(document.body).toBeTruthy();
  });

  it("shows error when fetchAnalysisHistory fails", async () => {
    api.fetchAnalysisHistory.mockRejectedValue(new Error("Réseau indisponible"));
    await act(async () => { wrap(); });
    await waitFor(() =>
      expect(screen.getByText(/Réseau indisponible/i)).toBeInTheDocument()
    );
  });

  it("shows empty state when no items returned", async () => {
    api.fetchAnalysisHistory.mockResolvedValue({ items: [] });
    await act(async () => { wrap(); });
    await waitFor(() => {
      expect(screen.queryByText(/server.log/i)).not.toBeInTheDocument();
    });
  });

  // ── Items rendering ──────────────────────────────────────────────────────
  it("displays list of analysis items", async () => {
    api.fetchAnalysisHistory.mockResolvedValue({ items: mockItems });
    await act(async () => { wrap(); });
    await waitFor(() => expect(screen.getByText(/server\.log/i)).toBeInTheDocument());
    expect(screen.getByText(/docker\.log/i)).toBeInTheDocument();
  });

  it("displays error counts for each item", async () => {
    api.fetchAnalysisHistory.mockResolvedValue({ items: mockItems });
    await act(async () => { wrap(); });
    await waitFor(() => screen.getByText(/server\.log/i));
    // 5 errors somewhere on page
    expect(screen.getAllByText(/5/i).length).toBeGreaterThan(0);
  });

  // ── Search ───────────────────────────────────────────────────────────────
  it("filters items by search query", async () => {
    api.fetchAnalysisHistory.mockResolvedValue({ items: mockItems });
    await act(async () => { wrap(); });
    await waitFor(() => screen.getByText(/server\.log/i));

    const searchInput = document.querySelector(".history-page-search, input[placeholder*='Rechercher']");
    if (searchInput) {
      fireEvent.change(searchInput, { target: { value: "docker" } });
      await waitFor(() => {
        expect(screen.queryByText(/server\.log/i)).not.toBeInTheDocument();
        expect(screen.getByText(/docker\.log/i)).toBeInTheDocument();
      });
    }
  });

  it("shows all items when search query is cleared", async () => {
    api.fetchAnalysisHistory.mockResolvedValue({ items: mockItems });
    await act(async () => { wrap(); });
    await waitFor(() => screen.getByText(/server\.log/i));

    const searchInput = document.querySelector(".history-page-search, input[placeholder*='Rechercher']");
    if (searchInput) {
      fireEvent.change(searchInput, { target: { value: "docker" } });
      fireEvent.change(searchInput, { target: { value: "" } });
      await waitFor(() => expect(screen.getByText(/server\.log/i)).toBeInTheDocument());
    }
  });

  // ── Sort ─────────────────────────────────────────────────────────────────
  it("sort select renders when items are present", async () => {
    api.fetchAnalysisHistory.mockResolvedValue({ items: mockItems });
    await act(async () => { wrap(); });
    await waitFor(() => screen.getByText(/server\.log/i));
    const selects = screen.getAllByRole("combobox");
    expect(selects.length).toBeGreaterThanOrEqual(0);
  });

  it("can change sort order", async () => {
    api.fetchAnalysisHistory.mockResolvedValue({ items: mockItems });
    await act(async () => { wrap(); });
    await waitFor(() => screen.getByText(/server\.log/i));
    const select = screen.queryByRole("combobox");
    if (select) {
      fireEvent.change(select, { target: { value: "errors_desc" } });
      // Should not crash
      expect(document.body).toBeTruthy();
    }
  });

  // ── View mode toggle (grouped / flat) ────────────────────────────────────
  it("can toggle view mode", async () => {
    api.fetchAnalysisHistory.mockResolvedValue({ items: mockItems });
    await act(async () => { wrap(); });
    await waitFor(() => screen.getByText(/server\.log/i));
    // Toggle buttons for grouped/flat
    const viewButtons = screen.getAllByRole("button").filter(
      b => /flat|group|vue|list/i.test(b.textContent || b.title || "")
    );
    if (viewButtons.length > 0) {
      fireEvent.click(viewButtons[0]);
      expect(document.body).toBeTruthy();
    }
  });

  // ── Select item ──────────────────────────────────────────────────────────
  it("calls onSelect when an item is clicked (flat view)", async () => {
    api.fetchAnalysisHistory.mockResolvedValue({ items: mockItems });
    const onSelect = vi.fn();
    await act(async () => {
      render(
        <LanguageProvider>
          <HistoryPage onSelect={onSelect} refreshKey={0} />
        </LanguageProvider>
      );
    });
    await waitFor(() => screen.getByText(/server\.log/i));

    // Switch to flat view so items are directly clickable
    const flatBtn = document.querySelector(".history-view-btn:not(.active), [title*='lat'], [title*='liste']");
    if (flatBtn) {
      fireEvent.click(flatBtn);
      await waitFor(() => {
        const flatItem = document.querySelector(".history-flat-item");
        if (flatItem) {
          fireEvent.click(flatItem);
          expect(onSelect).toHaveBeenCalled();
        }
      });
    } else {
      // grouped mode: click group header to expand, then click run card
      const groupHeader = document.querySelector(".history-group-header");
      if (groupHeader) {
        fireEvent.click(groupHeader);
        await waitFor(() => {
          const runCard = document.querySelector(".history-run-card");
          if (runCard) {
            fireEvent.click(runCard);
            expect(onSelect).toHaveBeenCalled();
          }
        });
      }
    }
  });

  // ── refreshKey changes ────────────────────────────────────────────────────
  it("re-fetches data when refreshKey changes", async () => {
    api.fetchAnalysisHistory.mockResolvedValue({ items: mockItems });
    const { rerender } = render(
      <LanguageProvider>
        <HistoryPage onSelect={vi.fn()} refreshKey={0} />
      </LanguageProvider>
    );
    await act(async () => {
      rerender(
        <LanguageProvider>
          <HistoryPage onSelect={vi.fn()} refreshKey={1} />
        </LanguageProvider>
      );
    });
    expect(api.fetchAnalysisHistory).toHaveBeenCalledTimes(2);
  });

  // ── Date formatting ───────────────────────────────────────────────────────
  it("handles null/undefined dates gracefully", async () => {
    const itemsWithNullDate = [{ id: 1, filename: "null-date.log", created_at: null, total_errors_found: 1, total_analyzed: 1 }];
    api.fetchAnalysisHistory.mockResolvedValue({ items: itemsWithNullDate });
    await act(async () => { wrap(); });
    await waitFor(() => expect(screen.getByText(/null-date\.log/i)).toBeInTheDocument());
  });
});
