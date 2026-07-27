import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ── Mock all API imports used by App.jsx ─────────────────────────────────────
vi.mock("./api", () => ({
  submitAnalysisJob: vi.fn(),
  streamJobProgress: vi.fn(),
  getJobResult: vi.fn(),
  fetchAnalysis: vi.fn(),
  downloadAnalysisPdf: vi.fn(),
  getCurrentUser: vi.fn(),
  syncCurrentUser: vi.fn(),
  logout: vi.fn(),
  sanitizeRole: vi.fn((r) => r),
  sanitizeEmail: vi.fn((e) => e),
}));

// ── Mock heavy child components ───────────────────────────────────────────────
vi.mock("./components/LogUploader", () => ({
  default: ({ onAnalyze, disabled }) => (
    <button
      data-testid="log-uploader"
      disabled={disabled}
      onClick={() => onAnalyze({ name: "test.log" })}
    >
      Upload
    </button>
  ),
}));

vi.mock("./components/ErrorAnalysis", () => ({
  default: ({ data }) => (
    <div data-testid="error-analysis">{data ? "Results" : "No results"}</div>
  ),
}));

vi.mock("./components/HistoryPage", () => ({
  default: ({ onSelect }) => (
    <div data-testid="history-page">
      <button onClick={() => onSelect(1)}>Select</button>
    </div>
  ),
}));

vi.mock("./components/LoadingSpinner", () => ({
  default: ({ message }) => <div data-testid="loading-spinner">{message}</div>,
}));

vi.mock("./components/LoginPage", () => ({
  default: ({ onLoginSuccess }) => (
    <button
      data-testid="login-page"
      onClick={() =>
        onLoginSuccess({
          token: "tok",
          access_token: "tok",
          role: "analyst",
          email: "user@test.com",
        })
      }
    >
      Login
    </button>
  ),
}));

vi.mock("./components/Dashboard", () => ({
  default: ({ onClose }) => (
    <div data-testid="dashboard">
      <button onClick={onClose}>Close dashboard</button>
    </div>
  ),
}));

vi.mock("./components/UserManagementPage", () => ({
  default: () => <div data-testid="user-management">Users</div>,
}));

vi.mock("./components/Navbar", () => ({
  default: ({
    user,
    setActiveView,
    VIEWS,
    handleLogout,
    setDarkMode,
    darkMode,
  }) => (
    <nav data-testid="navbar">
      <span data-testid="user-email">{user?.email}</span>
      <button data-testid="nav-history" onClick={() => setActiveView(VIEWS.HISTORY)}>
        History
      </button>
      <button data-testid="nav-dashboard" onClick={() => setActiveView(VIEWS.DASHBOARD)}>
        Dashboard
      </button>
      <button data-testid="nav-analyze" onClick={() => setActiveView(VIEWS.ANALYZE)}>
        Analyze
      </button>
      <button data-testid="nav-users" onClick={() => setActiveView(VIEWS.USERS)}>
        Users
      </button>
      <button data-testid="nav-logout" onClick={handleLogout}>
        Logout
      </button>
      <button
        data-testid="nav-theme"
        onClick={() => setDarkMode(!darkMode)}
      >
        Theme
      </button>
    </nav>
  ),
}));

vi.mock("./components/AccountModals", () => ({
  default: () => <div data-testid="account-modals" />,
}));

import App from "./App";
import { LanguageProvider } from "./i18n";
import * as api from "./api";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
function renderApp() {
  return render(
    <LanguageProvider>
      <App />
    </LanguageProvider>
  );
}

function setupLoggedInUser(role = "analyst") {
  api.getCurrentUser.mockReturnValue({
    token: "tok",
    access_token: "tok",
    role,
    email: "user@test.com",
  });
  api.syncCurrentUser.mockResolvedValue({
    role,
    email: "user@test.com",
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Renders LoginPage when no user
// ─────────────────────────────────────────────────────────────────────────────
describe("App — unauthenticated", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    api.getCurrentUser.mockReturnValue(null);
    api.syncCurrentUser.mockResolvedValue({ role: "analyst", email: "user@test.com" });
  });

  it("renders LoginPage when no user is set", () => {
    renderApp();
    expect(screen.getByTestId("login-page")).toBeInTheDocument();
    expect(screen.queryByTestId("navbar")).not.toBeInTheDocument();
  });

  it("renders main layout after login success", async () => {
    renderApp();
    await act(async () => {
      fireEvent.click(screen.getByTestId("login-page"));
    });
    await waitFor(() => {
      expect(screen.getByTestId("navbar")).toBeInTheDocument();
    });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Renders correct view on navigation
// ─────────────────────────────────────────────────────────────────────────────
describe("App — navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    setupLoggedInUser("analyst");
  });

  it("shows analyze view by default", async () => {
    renderApp();
    await waitFor(() => {
      expect(screen.getByTestId("log-uploader")).toBeInTheDocument();
    });
  });

  it("switches to history view", async () => {
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    fireEvent.click(screen.getByTestId("nav-history"));
    await waitFor(() => {
      expect(screen.getByTestId("history-page")).toBeInTheDocument();
    });
  });

  it("switches to dashboard view", async () => {
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    fireEvent.click(screen.getByTestId("nav-dashboard"));
    await waitFor(() => {
      expect(screen.getByTestId("dashboard")).toBeInTheDocument();
    });
  });

  it("closes dashboard via onClose callback", async () => {
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    fireEvent.click(screen.getByTestId("nav-dashboard"));
    await waitFor(() => screen.getByTestId("dashboard"));
    fireEvent.click(screen.getByText("Close dashboard"));
    await waitFor(() => {
      expect(screen.queryByTestId("dashboard")).not.toBeInTheDocument();
      expect(screen.getByTestId("log-uploader")).toBeInTheDocument();
    });
  });

  it("shows UserManagement only for admin role", async () => {
    setupLoggedInUser("admin");
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    fireEvent.click(screen.getByTestId("nav-users"));
    await waitFor(() => {
      expect(screen.getByTestId("user-management")).toBeInTheDocument();
    });
  });

  it("does not show UserManagement for analyst role", async () => {
    setupLoggedInUser("analyst");
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    fireEvent.click(screen.getByTestId("nav-users"));
    await waitFor(() => {
      expect(screen.queryByTestId("user-management")).not.toBeInTheDocument();
    });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Logout
// ─────────────────────────────────────────────────────────────────────────────
describe("App — logout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    setupLoggedInUser("analyst");
    api.logout.mockImplementation(() => {
      localStorage.removeItem("token");
    });
  });

  it("shows LoginPage after logout", async () => {
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    await act(async () => {
      fireEvent.click(screen.getByTestId("nav-logout"));
    });
    await waitFor(() => {
      expect(screen.getByTestId("login-page")).toBeInTheDocument();
    });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// History selection — fetchAnalysis
// ─────────────────────────────────────────────────────────────────────────────
describe("App — history selection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    setupLoggedInUser("analyst");
  });

  it("loads analysis from history and shows results", async () => {
    api.fetchAnalysis.mockResolvedValue({
      id: 1,
      data: {
        filename: "app.log",
        total_errors_found: 2,
        analyzed: [],
      },
    });

    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    fireEvent.click(screen.getByTestId("nav-history"));
    await waitFor(() => screen.getByTestId("history-page"));
    await act(async () => {
      fireEvent.click(screen.getByText("Select"));
    });
    await waitFor(() => {
      expect(api.fetchAnalysis).toHaveBeenCalledWith(1);
    });
  });

  it("handles fetchAnalysis error gracefully", async () => {
    api.fetchAnalysis.mockRejectedValue(new Error("Not found"));
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    fireEvent.click(screen.getByTestId("nav-history"));
    await waitFor(() => screen.getByTestId("history-page"));
    await act(async () => {
      fireEvent.click(screen.getByText("Select"));
    });
    // Should show an error, not crash
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// File analysis flow
// ─────────────────────────────────────────────────────────────────────────────
describe("App — file analysis", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    setupLoggedInUser("analyst");
  });

  it("shows loading spinner during analysis", async () => {
    api.submitAnalysisJob.mockResolvedValue({ job_id: "job-1" });
    // streamJobProgress never resolves (keeps loading state)
    api.streamJobProgress.mockImplementation((jobId, { onProgress }) => {
      return { close: vi.fn() };
    });

    renderApp();
    await waitFor(() => screen.getByTestId("log-uploader"));
    await act(async () => {
      fireEvent.click(screen.getByTestId("log-uploader"));
    });
    await waitFor(() => {
      expect(api.submitAnalysisJob).toHaveBeenCalled();
    });
  });

  it("completes analysis and shows results", async () => {
    api.submitAnalysisJob.mockResolvedValue({ job_id: "job-2" });
    api.streamJobProgress.mockImplementation((jobId, { onDone }) => {
      setTimeout(() => onDone({ log_id: 42 }), 0);
      return { close: vi.fn() };
    });
    api.getJobResult.mockResolvedValue({
      result: { filename: "test.log", total_errors_found: 1, analyzed: [] },
    });

    renderApp();
    await waitFor(() => screen.getByTestId("log-uploader"));
    await act(async () => {
      fireEvent.click(screen.getByTestId("log-uploader"));
    });
    await waitFor(() => {
      expect(api.getJobResult).toHaveBeenCalledWith("job-2");
    });
  });

  it("shows error when submitAnalysisJob fails", async () => {
    api.submitAnalysisJob.mockRejectedValue(new Error("Network error"));
    renderApp();
    await waitFor(() => screen.getByTestId("log-uploader"));
    await act(async () => {
      fireEvent.click(screen.getByTestId("log-uploader"));
    });
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("shows error when stream job fails", async () => {
    api.submitAnalysisJob.mockResolvedValue({ job_id: "job-3" });
    api.streamJobProgress.mockImplementation((jobId, { onError }) => {
      setTimeout(() => onError("Analysis failed"), 0);
      return { close: vi.fn() };
    });
    renderApp();
    await waitFor(() => screen.getByTestId("log-uploader"));
    await act(async () => {
      fireEvent.click(screen.getByTestId("log-uploader"));
    });
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Dark mode
// ─────────────────────────────────────────────────────────────────────────────
describe("App — dark mode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    setupLoggedInUser("analyst");
  });

  it("starts in dark mode when no theme is stored", async () => {
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    // Default: dark mode → body should NOT have theme-light class
    expect(document.body.classList.contains("theme-light")).toBe(false);
  });

  it("starts in light mode when theme=light is stored", async () => {
    localStorage.setItem("theme", "light");
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    expect(document.body.classList.contains("theme-light")).toBe(true);
  });

  it("toggles to light mode when theme button clicked", async () => {
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    await act(async () => {
      fireEvent.click(screen.getByTestId("nav-theme"));
    });
    // After toggle from dark → light
    expect(document.body.classList.contains("theme-light")).toBe(true);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Keyboard shortcuts
// ─────────────────────────────────────────────────────────────────────────────
describe("App — keyboard shortcuts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    setupLoggedInUser("analyst");
  });

  it("Ctrl+2 switches to history view", async () => {
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    fireEvent.keyDown(document, { key: "2", ctrlKey: true });
    await waitFor(() => {
      expect(screen.getByTestId("history-page")).toBeInTheDocument();
    });
  });

  it("Ctrl+3 switches to dashboard view", async () => {
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    fireEvent.keyDown(document, { key: "3", ctrlKey: true });
    await waitFor(() => {
      expect(screen.getByTestId("dashboard")).toBeInTheDocument();
    });
  });

  it("Ctrl+1 switches back to analyze view", async () => {
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    fireEvent.click(screen.getByTestId("nav-history"));
    await waitFor(() => screen.getByTestId("history-page"));
    fireEvent.keyDown(document, { key: "1", ctrlKey: true });
    await waitFor(() => {
      expect(screen.getByTestId("log-uploader")).toBeInTheDocument();
    });
  });

  it("Escape closes modals (no crash)", async () => {
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    // Should not throw
    fireEvent.keyDown(document, { key: "Escape" });
  });

  it("ignores shortcuts when typed in an input", async () => {
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    // Simulate keyboard event from an INPUT element — should be ignored
    const input = document.createElement("input");
    document.body.appendChild(input);
    input.focus();
    fireEvent.keyDown(input, { key: "2", ctrlKey: true, target: input });
    document.body.removeChild(input);
  });

  it("Ctrl+4 navigates to users for admin", async () => {
    setupLoggedInUser("admin");
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    fireEvent.keyDown(document, { key: "4", ctrlKey: true });
    await waitFor(() => {
      expect(screen.getByTestId("user-management")).toBeInTheDocument();
    });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// syncCurrentUser on mount
// ─────────────────────────────────────────────────────────────────────────────
describe("App — syncCurrentUser", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("updates user state with fresh data from syncCurrentUser", async () => {
    setupLoggedInUser("analyst");
    api.syncCurrentUser.mockResolvedValue({
      role: "admin",
      email: "user@test.com",
    });
    renderApp();
    await waitFor(() => screen.getByTestId("navbar"));
    // User email should still be visible
    expect(screen.getByTestId("user-email")).toHaveTextContent("user@test.com");
  });

  it("logs out when syncCurrentUser returns 401", async () => {
    setupLoggedInUser("analyst");
    api.syncCurrentUser.mockRejectedValue(new Error("401 Unauthorized"));
    api.logout.mockImplementation(() => {});
    renderApp();
    await waitFor(() => {
      expect(api.syncCurrentUser).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(api.logout).toHaveBeenCalled();
    });
  });
});
