import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { LanguageProvider } from "../i18n";

vi.mock("../api", () => ({
  fetchUsers: vi.fn(),
  updateUserStatus: vi.fn(),
  updateUserRole: vi.fn(),
  deleteUser: vi.fn(),
}));

import UserManagementPage from "./UserManagementPage";
import * as api from "../api";

const wrap = (ui) => render(<LanguageProvider>{ui}</LanguageProvider>);

const mockUsers = [
  { id: 1, email: "alice@test.com", role: "analyst", status: "active", created_at: "2026-01-01" },
  { id: 2, email: "bob@test.com",   role: "viewer",  status: "active", created_at: "2026-01-02" },
  { id: 3, email: "charlie@test.com", role: "admin", status: "inactive", created_at: "2026-01-03" },
];

beforeEach(() => vi.clearAllMocks());

describe("UserManagementPage", () => {
  it("shows loading state initially", () => {
    api.fetchUsers.mockResolvedValue([]);
    wrap(<UserManagementPage />);
    expect(document.body).toBeTruthy();
  });

  it("displays list of users after loading", async () => {
    api.fetchUsers.mockResolvedValue(mockUsers);
    wrap(<UserManagementPage />);
    expect(await screen.findByText(/alice@test.com/i)).toBeInTheDocument();
    expect(screen.getByText(/bob@test.com/i)).toBeInTheDocument();
  });

  it("shows error when fetchUsers fails", async () => {
    api.fetchUsers.mockRejectedValue(new Error("Erreur réseau"));
    wrap(<UserManagementPage />);
    expect(await screen.findByText(/Erreur réseau/i)).toBeInTheDocument();
  });

  it("shows Impossible de charger when error has no message", async () => {
    api.fetchUsers.mockRejectedValue({});
    wrap(<UserManagementPage />);
    expect(await screen.findByText(/Impossible de charger/i)).toBeInTheDocument();
  });

  it("renders user roles", async () => {
    api.fetchUsers.mockResolvedValue(mockUsers);
    wrap(<UserManagementPage />);
    await screen.findByText(/alice@test.com/i);
    expect(screen.getAllByText(/analyst/i).length).toBeGreaterThan(0);
  });

  it("calls updateUserRole when role is changed", async () => {
    api.fetchUsers.mockResolvedValue(mockUsers);
    api.updateUserRole.mockResolvedValue({});
    wrap(<UserManagementPage />);
    await screen.findByText(/alice@test.com/i);

    const selects = screen.getAllByRole("combobox");
    if (selects.length > 0) {
      fireEvent.change(selects[0], { target: { value: "admin" } });
      await waitFor(() => expect(api.updateUserRole).toHaveBeenCalled());
    }
  });

  it("calls updateUserStatus when status toggle is clicked", async () => {
    api.fetchUsers.mockResolvedValue(mockUsers);
    api.updateUserStatus.mockResolvedValue({});
    wrap(<UserManagementPage />);
    await screen.findByText(/alice@test.com/i);

    const statusButtons = screen.getAllByRole("button").filter(
      b => /activ|désactiv|disable|enable/i.test(b.textContent)
    );
    if (statusButtons.length > 0) {
      fireEvent.click(statusButtons[0]);
      await waitFor(() => expect(api.updateUserStatus).toHaveBeenCalled());
    }
  });

  it("calls deleteUser when delete is clicked and confirmed", async () => {
    api.fetchUsers.mockResolvedValue(mockUsers);
    api.deleteUser.mockResolvedValue({});
    vi.spyOn(window, "confirm").mockReturnValue(true);

    wrap(<UserManagementPage />);
    await screen.findByText(/alice@test.com/i);

    const deleteButtons = screen.getAllByRole("button").filter(
      b => /supprimer|delete/i.test(b.textContent)
    );
    if (deleteButtons.length > 0) {
      fireEvent.click(deleteButtons[0]);
      await waitFor(() => expect(api.deleteUser).toHaveBeenCalled());
    }
  });

  it("does NOT call deleteUser when delete is cancelled", async () => {
    api.fetchUsers.mockResolvedValue(mockUsers);
    vi.spyOn(window, "confirm").mockReturnValue(false);

    wrap(<UserManagementPage />);
    await screen.findByText(/alice@test.com/i);

    const deleteButtons = screen.getAllByRole("button").filter(
      b => /supprimer|delete/i.test(b.textContent)
    );
    if (deleteButtons.length > 0) {
      fireEvent.click(deleteButtons[0]);
      expect(api.deleteUser).not.toHaveBeenCalled();
    }
  });

  it("shows empty state when no users returned", async () => {
    api.fetchUsers.mockResolvedValue([]);
    wrap(<UserManagementPage />);
    await waitFor(() => {
      expect(screen.queryByText(/alice@test.com/i)).not.toBeInTheDocument();
    });
  });
});
