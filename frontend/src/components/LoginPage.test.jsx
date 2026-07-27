import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import LoginPage from "./LoginPage";
import { LanguageProvider } from "../i18n";

vi.mock("../api", () => ({
  login: vi.fn(),
  register: vi.fn(),
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
}));

import * as api from "../api";

const wrap = (ui) => render(<LanguageProvider>{ui}</LanguageProvider>);

beforeEach(() => {
  vi.clearAllMocks();
});

// ── Login view ─────────────────────────────────────────────────────────────
describe("LoginPage — login view", () => {
  it("renders email and password fields", () => {
    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    expect(screen.getByLabelText(/Adresse email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Mot de passe/i)).toBeInTheDocument();
  });

  it("renders Se connecter submit button by default", () => {
    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Se connecter/i })).toBeInTheDocument();
  });

  it("calls onLoginSuccess with user data on successful login", async () => {
    const onLoginSuccess = vi.fn();
    api.login.mockResolvedValue({ access_token: "tok", role: "analyst", email: "u@e.com" });

    wrap(<LoginPage onLoginSuccess={onLoginSuccess} />);
    fireEvent.change(screen.getByLabelText(/Adresse email/i), { target: { value: "user@example.com" } });
    fireEvent.change(screen.getByLabelText(/Mot de passe/i), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: /Se connecter/i }));

    await waitFor(() => expect(onLoginSuccess).toHaveBeenCalledWith(
      expect.objectContaining({ access_token: "tok" })
    ));
  });

  it("displays error message on login failure", async () => {
    api.login.mockRejectedValue(new Error("Email ou mot de passe incorrect"));

    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/Adresse email/i), { target: { value: "bad@example.com" } });
    fireEvent.change(screen.getByLabelText(/Mot de passe/i), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /Se connecter/i }));

    expect(await screen.findByText(/Email ou mot de passe incorrect/i)).toBeInTheDocument();
  });

  it("shows forgot password link", () => {
    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    expect(screen.getByText(/Mot de passe oubli/i)).toBeInTheDocument();
  });

  it("sets forgotEmail from current email when clicking forgot password", () => {
    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/Adresse email/i), { target: { value: "prefill@example.com" } });
    fireEvent.click(screen.getByText(/Mot de passe oubli/i));
    const emailInput = screen.getByLabelText(/Adresse email/i);
    expect(emailInput.value).toBe("prefill@example.com");
  });
});

// ── Register view ──────────────────────────────────────────────────────────
describe("LoginPage — register view", () => {
  const switchToRegister = () => {
    fireEvent.click(screen.getByRole("button", { name: /Nouveau/i }));
  };

  it("shows register form (org name field) when toggled", () => {
    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    switchToRegister();
    expect(screen.getByLabelText(/Nom de l.organisation/i)).toBeInTheDocument();
  });

  it("shows S inscrire button on register view", () => {
    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    switchToRegister();
    expect(screen.getByRole("button", { name: /inscrire/i })).toBeInTheDocument();
  });

  it("auto-generates slug from organisation name", () => {
    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    switchToRegister();
    fireEvent.change(screen.getByLabelText(/Nom de l.organisation/i), { target: { value: "Acme Corp" } });
    expect(screen.getByLabelText(/Slug/i).value).toBe("acme-corp");
  });

  it("does not call api.register when org name is missing (internal validation)", () => {
    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    switchToRegister();

    fireEvent.change(screen.getByLabelText(/Adresse email/i), { target: { value: "new@example.com" } });
    fireEvent.change(screen.getAllByLabelText(/Mot de passe/i)[0], { target: { value: "Pass123!" } });
    fireEvent.click(screen.getByRole("button", { name: /inscrire/i }));

    expect(api.register).not.toHaveBeenCalled();
  });

  it("calls register API with all fields on valid submit", async () => {
    api.register.mockResolvedValue({ access_token: "tok", role: "admin", email: "new@example.com" });
    const onLoginSuccess = vi.fn();
    wrap(<LoginPage onLoginSuccess={onLoginSuccess} />);
    switchToRegister();

    fireEvent.change(screen.getByLabelText(/Adresse email/i), { target: { value: "new@example.com" } });
    fireEvent.change(screen.getAllByLabelText(/Mot de passe/i)[0], { target: { value: "Pass123!" } });
    fireEvent.change(screen.getByLabelText(/Nom de l.organisation/i), { target: { value: "My Org" } });

    fireEvent.click(screen.getByRole("button", { name: /inscrire/i }));

    await waitFor(() => expect(api.register).toHaveBeenCalledWith(
      "new@example.com", "Pass123!", "My Org", "my-org", "viewer"
    ));
  });

  it("can toggle back to login view", () => {
    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    switchToRegister();
    fireEvent.click(screen.getByRole("button", { name: /Vous avez d.j/i }));
    expect(screen.getByRole("button", { name: /Se connecter/i })).toBeInTheDocument();
  });
});

// ── Forgot password view ───────────────────────────────────────────────────
describe("LoginPage — forgot password view", () => {
  const switchToForgot = () => {
    fireEvent.click(screen.getByText(/Mot de passe oubli/i));
  };

  it("shows forgot form with Envoyer le code button", () => {
    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    switchToForgot();
    expect(screen.getByRole("button", { name: /Envoyer le code/i })).toBeInTheDocument();
  });

  it("calls forgotPassword API on submit", async () => {
    api.forgotPassword.mockResolvedValue({ message: "code envoye" });
    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    switchToForgot();

    fireEvent.change(screen.getByLabelText(/Adresse email/i), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /Envoyer le code/i }));

    await waitFor(() => expect(api.forgotPassword).toHaveBeenCalledWith("user@example.com"));
  });

  it("switches to reset view after successful forgot request", async () => {
    api.forgotPassword.mockResolvedValue({ message: "ok" });
    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    switchToForgot();

    fireEvent.change(screen.getByLabelText(/Adresse email/i), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /Envoyer le code/i }));

    expect(await screen.findByRole("button", { name: /Mettre/i })).toBeInTheDocument();
  });

  it("shows error message when forgot password fails", async () => {
    api.forgotPassword.mockRejectedValue(new Error("Trop de demandes"));
    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    switchToForgot();

    fireEvent.change(screen.getByLabelText(/Adresse email/i), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /Envoyer le code/i }));

    expect(await screen.findByText(/Trop de demandes/i)).toBeInTheDocument();
  });

  it("back button returns to login view", () => {
    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    switchToForgot();
    fireEvent.click(screen.getByText(/Retour/i));
    expect(screen.getByRole("button", { name: /Se connecter/i })).toBeInTheDocument();
  });
});

// ── Reset password view ────────────────────────────────────────────────────
describe("LoginPage — reset password view", () => {
  const goToReset = async () => {
    api.forgotPassword.mockResolvedValue({ message: "ok" });
    wrap(<LoginPage onLoginSuccess={vi.fn()} />);
    fireEvent.click(screen.getByText(/Mot de passe oubli/i));
    fireEvent.change(screen.getByLabelText(/Adresse email/i), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /Envoyer le code/i }));
    await screen.findByRole("button", { name: /Mettre/i });
  };

  it("shows reset form with Mettre a jour button", async () => {
    await goToReset();
    expect(screen.getByRole("button", { name: /Mettre/i })).toBeInTheDocument();
  });

  it("shows mismatch error when passwords dont match", async () => {
    await goToReset();

    fireEvent.change(document.getElementById("new-password"), { target: { value: "password1" } });
    fireEvent.change(document.getElementById("confirm-password"), { target: { value: "password2" } });

    const form = document.querySelector("form.login-form");
    fireEvent.submit(form);

    expect(await screen.findByText(/Les mots de passe ne correspondent pas/i)).toBeInTheDocument();
  });

  it("calls resetPassword API when passwords match", async () => {
    api.resetPassword.mockResolvedValue({ message: "ok" });
    await goToReset();

    fireEvent.change(document.getElementById("otp-code"), { target: { value: "123456" } });
    fireEvent.change(document.getElementById("new-password"), { target: { value: "NewPass123!" } });
    fireEvent.change(document.getElementById("confirm-password"), { target: { value: "NewPass123!" } });

    fireEvent.click(screen.getByRole("button", { name: /Mettre/i }));

    await waitFor(() => expect(api.resetPassword).toHaveBeenCalledWith(
      "user@example.com", "123456", "NewPass123!"
    ));
  });

  it("back button renvoyer le code returns to forgot view", async () => {
    await goToReset();
    fireEvent.click(screen.getByText(/Renvoyer le code/i));
    expect(screen.getByRole("button", { name: /Envoyer le code/i })).toBeInTheDocument();
  });
});
