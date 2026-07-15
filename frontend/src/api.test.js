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
