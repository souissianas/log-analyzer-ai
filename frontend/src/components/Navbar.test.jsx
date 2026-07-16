import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Navbar from "./Navbar";

// ANALYZE et USERS ajoutés : le composant réel boucle sur VIEWS.ANALYZE et,
// pour un admin, sur VIEWS.USERS. Sans ces clés, item.id valait `undefined`
// pour deux items -> React levait "Each child in a list should have a
// unique key prop" (clés dupliquées à undefined).
const VIEWS = { ANALYZE: "analyze", HISTORY: "history", DASHBOARD: "dashboard", USERS: "users" };

const defaultProps = {
  user: { email: "admin@test.com", role: "admin" },
  activeView: "upload",
  setActiveView: vi.fn(),
  loading: false,
  loadingMessage: "",
  language: "fr",
  setLanguage: vi.fn(),
  darkMode: false,
  setDarkMode: vi.fn(),
  notifications: [],
  setNotifications: vi.fn(),
  lastLogin: null,
  formatLastLogin: vi.fn(() => "Jamais"),
  setShowAccountModal: vi.fn(),
  setShowSettingsModal: vi.fn(),
  handleLogout: vi.fn(),
  VIEWS,
  t: (k) => k,
};

beforeEach(() => vi.clearAllMocks());

describe("Navbar", () => {
  it("renders without crashing", () => {
    render(<Navbar {...defaultProps} />);
    expect(document.querySelector("nav, header, .navbar")).toBeTruthy();
  });

  it("displays user email", () => {
    render(<Navbar {...defaultProps} />);
    expect(screen.getByText(/admin@test.com/i)).toBeInTheDocument();
  });

  it("shows unread notification count when notifications exist", () => {
    const props = {
      ...defaultProps,
      notifications: [
        { id: 1, text: "Analyse terminée", time: "10:00", read: false },
        { id: 2, text: "Nouvelle alerte", time: "11:00", read: false },
      ],
    };
    render(<Navbar {...props} />);
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("does not show unread badge when all notifications are read", () => {
    const props = {
      ...defaultProps,
      notifications: [
        { id: 1, text: "Already read", time: "09:00", read: true },
      ],
    };
    render(<Navbar {...props} />);
    // No badge for unread count (= 0)
    expect(screen.queryByText("1")).not.toBeInTheDocument();
  });

  it("toggles profile menu on profile button click", () => {
    render(<Navbar {...defaultProps} />);
    // Profile button uses class .user-profile-card
    const profileBtn = document.querySelector(".user-profile-card");
    expect(profileBtn).toBeTruthy();
    fireEvent.click(profileBtn);
    // After click, .profile-dropdown should appear
    expect(document.querySelector(".profile-dropdown")).toBeTruthy();
  });

  it("calls handleLogout when logout button is clicked", () => {
    const handleLogout = vi.fn();
    render(<Navbar {...defaultProps} handleLogout={handleLogout} />);
    // Open profile menu first
    fireEvent.click(document.querySelector(".user-profile-card"));
    // Logout = .profile-dropdown-item.danger
    fireEvent.click(document.querySelector(".profile-dropdown-item.danger"));
    expect(handleLogout).toHaveBeenCalled();
  });

  it("shows navAnalyzing indicator when loading is true", () => {
    render(<Navbar {...defaultProps} loading={true} loadingMessage="Analyse en cours..." />);
    // loadingMessage is in the title attr; the visible text is t('navAnalyzing') = 'navAnalyzing'
    expect(document.querySelector(".nav-job-indicator")).toBeTruthy();
  });

  it("closes dropdowns on Escape key press", () => {
    render(<Navbar {...defaultProps} />);
    fireEvent.click(document.querySelector(".user-profile-card"));
    expect(document.querySelector(".profile-dropdown")).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(document.querySelector(".profile-dropdown")).not.toBeTruthy();
  });

  it("calls setDarkMode when dark mode toggle is clicked", () => {
    const setDarkMode = vi.fn();
    render(<Navbar {...defaultProps} setDarkMode={setDarkMode} />);
    // Le bouton n'a pas de classe dédiée (il partage "btn-icon-action" avec
    // le sélecteur de langue et la cloche), mais son `title` est unique :
    // t(darkMode ? 'navLightMode' : 'navDarkMode'). Avec darkMode=false et
    // t = k => k, le title vaut exactement "navDarkMode".
    const darkModeBtn = document.querySelector('button[title="navDarkMode"]');
    expect(darkModeBtn).toBeTruthy();
    fireEvent.click(darkModeBtn);
    expect(setDarkMode).toHaveBeenCalled();
  });

  it("shows notification panel when notification button is clicked", () => {
    const props = {
      ...defaultProps,
      notifications: [
        { id: 1, text: "Fichier analysé", time: "12:00", read: false },
      ],
    };
    render(<Navbar {...props} />);
    // Le bouton cloche a title={t('navNotifications')} -> "navNotifications"
    const notifBtn = document.querySelector('button[title="navNotifications"]');
    expect(notifBtn).toBeTruthy();
    fireEvent.click(notifBtn);
    expect(screen.getByText(/Fichier analysé/i)).toBeInTheDocument();
  });

  it("renders with viewer role", () => {
    const props = { ...defaultProps, user: { email: "viewer@test.com", role: "viewer" } };
    render(<Navbar {...props} />);
    expect(screen.getByText(/viewer@test.com/i)).toBeInTheDocument();
  });

  it("renders navigation links for VIEWS", () => {
    render(<Navbar {...defaultProps} />);
    // Should have navigation elements (buttons or links for views)
    const buttons = screen.getAllByRole("button");
    expect(buttons.length).toBeGreaterThan(0);
  });
});
