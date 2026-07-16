import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { sanitizeRole, sanitizeEmail } from "./api";

// ── sanitizeRole ────────────────────────────────────────────────────────────
describe("sanitizeRole", () => {
  it("returns admin for admin", () => {
    expect(sanitizeRole("admin")).toBe("admin");
  });
  it("returns analyst for analyst", () => {
    expect(sanitizeRole("analyst")).toBe("analyst");
  });
  it("returns viewer for viewer", () => {
    expect(sanitizeRole("viewer")).toBe("viewer");
  });
  it("returns null for unknown role", () => {
    expect(sanitizeRole("superadmin")).toBeNull();
  });
  it("returns null for empty string", () => {
    expect(sanitizeRole("")).toBeNull();
  });
  it("returns null for non-string", () => {
    expect(sanitizeRole(null)).toBeNull();
    expect(sanitizeRole(42)).toBeNull();
    expect(sanitizeRole(undefined)).toBeNull();
  });
});

// ── sanitizeEmail ───────────────────────────────────────────────────────────
describe("sanitizeEmail", () => {
  it("returns valid email as-is", () => {
    expect(sanitizeEmail("user@example.com")).toBe("user@example.com");
  });
  it("returns valid email with subdomain", () => {
    expect(sanitizeEmail("user@mail.example.com")).toBe("user@mail.example.com");
  });
  it("returns null for email without @", () => {
    expect(sanitizeEmail("notanemail")).toBeNull();
  });
  it("returns null for email without domain", () => {
    expect(sanitizeEmail("user@")).toBeNull();
  });
  it("returns null for empty string", () => {
    expect(sanitizeEmail("")).toBeNull();
  });
  it("returns null for non-string", () => {
    expect(sanitizeEmail(null)).toBeNull();
    expect(sanitizeEmail(42)).toBeNull();
  });
  it("returns null for excessively long email", () => {
    const longEmail = "a".repeat(250) + "@example.com";
    expect(sanitizeEmail(longEmail)).toBeNull();
  });
});

// ── login / register / logout ─────────────────────────────────────────────
describe("login", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
    localStorage.clear();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("stores token and returns data on success", async () => {
    const { login } = await import("./api");
    const fakeData = {
      access_token: "tok123",
      refresh_token: "ref456",
      role: "analyst",
      email: "user@example.com",
    };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => fakeData,
    });
    const result = await login("user@example.com", "password");
    expect(result.access_token).toBe("tok123");
    expect(localStorage.getItem("token")).toBe("tok123");
  });

  it("throws error on failed login", async () => {
    const { login } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Email ou mot de passe incorrect" }),
    });
    await expect(login("bad@example.com", "wrong")).rejects.toThrow(
      "Email ou mot de passe incorrect"
    );
  });

  it("throws fallback error message when no detail", async () => {
    const { login } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({}),
    });
    await expect(login("bad@example.com", "wrong")).rejects.toThrow(
      "Email ou mot de passe incorrect"
    );
  });
});

describe("register", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
    localStorage.clear();
  });

  it("stores token on successful registration", async () => {
    const { register } = await import("./api");
    const fakeData = {
      access_token: "regTok",
      refresh_token: "regRef",
      role: "admin",
      email: "admin@example.com",
    };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => fakeData,
    });
    const result = await register("admin@example.com", "pass", "Org", "org", "admin");
    expect(result.access_token).toBe("regTok");
    expect(localStorage.getItem("token")).toBe("regTok");
  });

  it("throws on registration failure", async () => {
    const { register } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Email deja utilise" }),
    });
    await expect(
      register("taken@example.com", "pass", "Org", "org")
    ).rejects.toThrow("Email deja utilise");
  });
});

describe("logout", () => {
  it("clears localStorage", async () => {
    const { logout } = await import("./api");
    localStorage.setItem("token", "tok");
    localStorage.setItem("role", "admin");
    localStorage.setItem("email", "user@example.com");
    logout();
    expect(localStorage.getItem("token")).toBeNull();
    expect(localStorage.getItem("role")).toBeNull();
    expect(localStorage.getItem("email")).toBeNull();
  });
});

describe("forgotPassword", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it("resolves on success", async () => {
    const { forgotPassword } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: "Si cet email existe, un code a ete envoye." }),
    });
    const result = await forgotPassword("user@example.com");
    expect(result.message).toContain("code");
  });

  it("throws on failure", async () => {
    const { forgotPassword } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Trop de demandes" }),
    });
    await expect(forgotPassword("user@example.com")).rejects.toThrow("Trop de demandes");
  });
});

describe("resetPassword", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it("resolves on success", async () => {
    const { resetPassword } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: "Mot de passe mis a jour avec succes." }),
    });
    const result = await resetPassword("user@example.com", "123456", "newpass");
    expect(result.message).toContain("succes");
  });

  it("throws on wrong code", async () => {
    const { resetPassword } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Code incorrect." }),
    });
    await expect(
      resetPassword("user@example.com", "000000", "newpass")
    ).rejects.toThrow("Code incorrect.");
  });
});

// ── getCurrentUser ───────────────────────────────────────────────────────────
describe("getCurrentUser", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("returns null if no token/role/email in localStorage", async () => {
    const { getCurrentUser } = await import("./api");
    expect(getCurrentUser()).toBeNull();
  });

  it("returns user object if all fields exist", async () => {
    const { getCurrentUser } = await import("./api");
    localStorage.setItem("token", "myToken");
    localStorage.setItem("role", "viewer");
    localStorage.setItem("email", "v@e.com");
    expect(getCurrentUser()).toEqual({
      token: "myToken",
      role: "viewer",
      email: "v@e.com",
    });
  });
});

// ── fetchCurrentUser & syncCurrentUser ────────────────────────────────────────
describe("fetchCurrentUser & syncCurrentUser", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
    localStorage.clear();
  });

  it("fetchCurrentUser returns data on success", async () => {
    const { fetchCurrentUser } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ email: "me@test.com", role: "admin" }),
    });
    const res = await fetchCurrentUser();
    expect(res.email).toBe("me@test.com");
  });

  it("fetchCurrentUser throws on failure", async () => {
    const { fetchCurrentUser } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
    });
    await expect(fetchCurrentUser()).rejects.toThrow();
  });

  it("syncCurrentUser fetches and persists user data", async () => {
    const { syncCurrentUser } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ email: "sync@test.com", role: "analyst" }),
    });
    const res = await syncCurrentUser();
    expect(res.email).toBe("sync@test.com");
    expect(localStorage.getItem("email")).toBe("sync@test.com");
    expect(localStorage.getItem("role")).toBe("analyst");
  });
});

// ── users CRUD functions ──────────────────────────────────────────────────────
describe("users CRUD functions", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it("fetchUsers fetches users list", async () => {
    const { fetchUsers } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [{ id: 1, email: "u1@e.com" }],
    });
    const res = await fetchUsers();
    expect(res).toEqual([{ id: 1, email: "u1@e.com" }]);
  });

  it("fetchUsers throws error on status failure", async () => {
    const { fetchUsers } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Pas autorisé" }),
    });
    await expect(fetchUsers()).rejects.toThrow("Pas autorisé");
  });

  it("updateUserStatus updates user status", async () => {
    const { updateUserStatus } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    });
    const res = await updateUserStatus(42, "inactive");
    expect(res.success).toBe(true);
  });

  it("updateUserStatus throws on error", async () => {
    const { updateUserStatus } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Erreur statut" }),
    });
    await expect(updateUserStatus(42, "inactive")).rejects.toThrow("Erreur statut");
  });

  it("updateUserRole updates user role", async () => {
    const { updateUserRole } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    });
    const res = await updateUserRole(42, "admin");
    expect(res.success).toBe(true);
  });

  it("updateUserRole throws on error", async () => {
    const { updateUserRole } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Erreur rôle" }),
    });
    await expect(updateUserRole(42, "admin")).rejects.toThrow("Erreur rôle");
  });

  it("deleteUser deletes user", async () => {
    const { deleteUser } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    });
    const res = await deleteUser(42);
    expect(res.success).toBe(true);
  });

  it("deleteUser throws on error", async () => {
    const { deleteUser } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Erreur suppression" }),
    });
    await expect(deleteUser(42)).rejects.toThrow("Erreur suppression");
  });
});

// ── Health checks ────────────────────────────────────────────────────────────
describe("Health checks", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it("checkHealth returns status", async () => {
    const { checkHealth } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok" }),
    });
    const res = await checkHealth();
    expect(res.status).toBe("ok");
  });

  it("checkHealth throws on error", async () => {
    const { checkHealth } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    });
    await expect(checkHealth()).rejects.toThrow("Backend indisponible (500)");
  });

  it("checkReadiness returns readiness status on success", async () => {
    const { checkReadiness } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ database: { ok: true } }),
    });
    const res = await checkReadiness();
    expect(res.ok).toBe(true);
    expect(res.database.ok).toBe(true);
  });

  it("checkReadiness returns ok false on failure", async () => {
    const { checkReadiness } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ database: { ok: false } }),
    });
    const res = await checkReadiness();
    expect(res.ok).toBe(false);
    expect(res.database.ok).toBe(false);
  });

  it("checkOllamaHealth returns health information", async () => {
    const { checkOllamaHealth } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ollama_running: true }),
    });
    const res = await checkOllamaHealth();
    expect(res.ollama_running).toBe(true);
  });

  it("checkOllamaHealth throws custom message on failure", async () => {
    const { checkOllamaHealth } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
      text: async () => "Ollama Server Down",
    });
    await expect(checkOllamaHealth()).rejects.toThrow("Ollama Server Down");
  });
});

// ── analysis files functions ──────────────────────────────────────────────────
describe("analysis files functions", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it("analyzeFile post file with FormData", async () => {
    const { analyzeFile } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ total_errors_found: 1 }),
    });
    const mockFile = new File(["test log content"], "test.log", { type: "text/plain" });
    const res = await analyzeFile(mockFile, 10);
    expect(res.total_errors_found).toBe(1);
  });

  it("analyzeFile throws on HTTP error", async () => {
    const { analyzeFile } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      text: async () => "Bad request details",
    });
    const mockFile = new File(["test log content"], "test.log", { type: "text/plain" });
    await expect(analyzeFile(mockFile)).rejects.toThrow("HTTP 400: Bad request details");
  });

  it("submitAnalysisJob posts job with file", async () => {
    const { submitAnalysisJob } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ job_id: "j-1" }),
    });
    const mockFile = new File(["test log content"], "test.log", { type: "text/plain" });
    const res = await submitAnalysisJob(mockFile, 5);
    expect(res.job_id).toBe("j-1");
  });

  it("submitAnalysisJob throws on HTTP error", async () => {
    const { submitAnalysisJob } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 413,
      text: async () => "Payload Too Large",
    });
    const mockFile = new File(["test log content"], "test.log", { type: "text/plain" });
    await expect(submitAnalysisJob(mockFile)).rejects.toThrow("HTTP 413: Payload Too Large");
  });

  it("getJobResult fetches results", async () => {
    const { getJobResult } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ filename: "test.log" }),
    });
    const res = await getJobResult("j-1");
    expect(res.filename).toBe("test.log");
  });

  it("getJobResult throws on failure", async () => {
    const { getJobResult } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
    });
    await expect(getJobResult("j-1")).rejects.toThrow("Résultat introuvable (404)");
  });

  it("fetchAnalysisHistory fetches logs list", async () => {
    const { fetchAnalysisHistory } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [] }),
    });
    const res = await fetchAnalysisHistory();
    expect(res.items).toEqual([]);
  });

  it("fetchAnalysisHistory throws on failure", async () => {
    const { fetchAnalysisHistory } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    });
    await expect(fetchAnalysisHistory()).rejects.toThrow("Impossible de charger l'historique (500)");
  });

  it("fetchAnalysis fetches specific log data", async () => {
    const { fetchAnalysis } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 42 }),
    });
    const res = await fetchAnalysis(42);
    expect(res.id).toBe(42);
  });

  it("fetchAnalysis throws on failure", async () => {
    const { fetchAnalysis } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
    });
    await expect(fetchAnalysis(42)).rejects.toThrow("Analyse introuvable (404)");
  });

  it("fetchDashboardStats returns stats", async () => {
    const { fetchDashboardStats } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ total_analyses: 12 }),
    });
    const res = await fetchDashboardStats();
    expect(res.total_analyses).toBe(12);
  });

  it("fetchDashboardStats throws on failure", async () => {
    const { fetchDashboardStats } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    });
    await expect(fetchDashboardStats()).rejects.toThrow("Impossible de charger le dashboard (500)");
  });

  it("exportPdfUrl returns expected URL", async () => {
    const { exportPdfUrl } = await import("./api");
    expect(exportPdfUrl(42)).toContain("/logs/42/export");
  });

  it("downloadAnalysisPdf creates temporary link to download", async () => {
    const { downloadAnalysisPdf } = await import("./api");
    const fakeBlob = new Blob(["%PDF-1.4"], { type: "application/pdf" });
    global.fetch.mockResolvedValueOnce({
      ok: true,
      blob: async () => fakeBlob,
    });

    // Mock URL functions
    const mockUrl = "blob:http://localhost:3000/123-456";
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => mockUrl),
      revokeObjectURL: vi.fn(),
    });

    // Mock HTMLAnchorElement click
    const mockAnchor = {
      href: "",
      download: "",
      click: vi.fn(),
    };
    vi.spyOn(document, "createElement").mockImplementation((tagName) => {
      if (tagName === "a") return mockAnchor;
      return {};
    });

    await downloadAnalysisPdf(42);

    expect(window.URL.createObjectURL).toHaveBeenCalledWith(fakeBlob);
    expect(mockAnchor.href).toBe(mockUrl);
    expect(mockAnchor.download).toBe("analysis_42.pdf");
    expect(mockAnchor.click).toHaveBeenCalled();
    expect(window.URL.revokeObjectURL).toHaveBeenCalledWith(mockUrl);
  });

  it("downloadAnalysisPdf throws on HTTP error", async () => {
    const { downloadAnalysisPdf } = await import("./api");
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
    });
    await expect(downloadAnalysisPdf(42)).rejects.toThrow("Export PDF impossible (403)");
  });
});

// ── streamJobProgress ────────────────────────────────────────────────────────
describe("streamJobProgress", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("handles successful SSE stream from connect to done", async () => {
    const { streamJobProgress } = await import("./api");
    
    const onProgress = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    const mockValues = [
      { done: false, value: new TextEncoder().encode("data: {\"status\":\"pending\",\"current\":5,\"total\":10}\n") },
      { done: false, value: new TextEncoder().encode("data: {\"status\":\"done\",\"log_id\":99}\n") }
    ];
    let callCount = 0;
    const mockReader = {
      read: vi.fn(() => Promise.resolve(mockValues[callCount++]))
    };

    global.fetch.mockResolvedValueOnce({
      ok: true,
      body: {
        getReader: () => mockReader
      }
    });

    const { close } = streamJobProgress("job-123", { onProgress, onDone, onError });

    // Attendre que la promesse de la connexion se résolve et consomme le flux
    await vi.runAllTimersAsync();

    expect(onProgress).toHaveBeenCalledWith({ status: "pending", current: 5, total: 10 });
    expect(onDone).toHaveBeenCalledWith({ status: "done", log_id: 99 });
    expect(onError).not.toHaveBeenCalled();
    close();
  });

  it("falls back to polling on non-ok SSE response", async () => {
    const { streamJobProgress } = await import("./api");

    const onProgress = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    // SSE connection fails (e.g. 500)
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 500
    });

    // Mock polling responses
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "pending", current: 1, total: 5 })
    });
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "done", log_id: 42 })
    });

    const { close } = streamJobProgress("job-123", { onProgress, onDone, onError });

    // Exécuter les timers pour déclencher le polling (qui attend 3s par itération)
    await vi.advanceTimersByTimeAsync(3500);
    expect(onProgress).toHaveBeenCalledWith({ status: "pending", current: 1, total: 5 });

    await vi.advanceTimersByTimeAsync(3500);
    expect(onDone).toHaveBeenCalledWith({ status: "done", log_id: 42 });

    close();
  });

  it("retries SSE on network error up to 3 times then falls back to polling", async () => {
    const { streamJobProgress } = await import("./api");

    const onProgress = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    // Mock network failures for 3 connection attempts
    global.fetch.mockRejectedValue(new Error("Network connection lost"));

    // Polling mock response
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ error: "job_not_found" })
    });

    const { close } = streamJobProgress("job-123", { onProgress, onDone, onError });

    // Attendre les 3 tentatives (espacées de SSE_RETRY_DELAY_MS = 3s)
    await vi.advanceTimersByTimeAsync(10000);

    // Puisque le polling a renvoyé job_not_found, onError doit être appelé
    expect(onError).toHaveBeenCalledWith("Job introuvable ou expiré");
    close();
  });
});


