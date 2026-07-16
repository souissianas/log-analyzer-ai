import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import AccountModals from './AccountModals'

const defaultProps = {
  showAccountModal: false,
  setShowAccountModal: vi.fn(),
  showSettingsModal: false,
  setShowSettingsModal: vi.fn(),
  user: { email: 'test@example.com', role: 'admin' },
  darkMode: false,
  setDarkMode: vi.fn(),
  t: (key) => {
    const translations = {
      modalClose: 'Fermer',
      accountTitle: 'Mon Compte',
      accountEmail: 'Adresse Email',
      accountRole: 'Rôle',
      accountPermissions: 'Permissions',
      roleDescAdmin: 'Description Admin',
      roleDescAnalyst: 'Description Analyste',
      roleDescViewer: 'Description Spectateur',
      settingsTitle: 'Paramètres',
      settingsTheme: 'Thème',
      settingsThemeDesc: 'Changer le thème',
      settingsThemeLightBtn: 'Mode Clair',
      settingsThemeDarkBtn: 'Mode Sombre',
      settingsModel: 'Modèle IA',
      settingsModelDesc: 'Modèle Ollama configuré',
      settingsData: 'Données de l\'application',
      settingsDataDesc: 'Réinitialiser toutes les données locales',
      settingsResetBtn: 'Réinitialiser',
      settingsResetConfirm: 'Voulez-vous vraiment réinitialiser toutes les données ?',
    }
    return translations[key] || key
  },
  language: 'fr',
}

describe('AccountModals Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('location', { reload: vi.fn() })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders nothing when both modals are closed', () => {
    const { container } = render(<AccountModals {...defaultProps} />)
    expect(container.firstChild).toBeNull()
  })

  // ── Tests Modale Mon Compte ──────────────────────────────────────────────
  describe('Account Modal', () => {
    const props = { ...defaultProps, showAccountModal: true }

    it('renders the account modal with user email and role info', () => {
      render(<AccountModals {...props} />)
      expect(screen.getByText('Mon Compte')).toBeInTheDocument()
      expect(screen.getByText('test@example.com')).toBeInTheDocument()
      expect(screen.getByText('admin')).toBeInTheDocument()
      expect(screen.getByText('Description Admin')).toBeInTheDocument()
    })

    it('displays roles-specific descriptions correctly', () => {
      const { rerender } = render(<AccountModals {...props} user={{ email: 'u@e.com', role: 'analyst' }} />)
      expect(screen.getByText('Description Analyste')).toBeInTheDocument()

      rerender(<AccountModals {...props} user={{ email: 'u@e.com', role: 'viewer' }} />)
      expect(screen.getByText('Description Spectateur')).toBeInTheDocument()
    })

    it('calls setShowAccountModal(false) when clicking the close button', () => {
      render(<AccountModals {...props} />)
      const closeBtn = document.querySelector('.modal-close-btn')
      expect(closeBtn).toBeInTheDocument()
      fireEvent.click(closeBtn)
      expect(props.setShowAccountModal).toHaveBeenCalledWith(false)
    })

    it('calls setShowAccountModal(false) when clicking the overlay backdrop', () => {
      render(<AccountModals {...props} />)
      const backdrop = document.querySelector('.modal-overlay-backdrop')
      expect(backdrop).toBeInTheDocument()
      fireEvent.click(backdrop)
      expect(props.setShowAccountModal).toHaveBeenCalledWith(false)
    })
  })

  // ── Tests Modale Paramètres ──────────────────────────────────────────────
  describe('Settings Modal', () => {
    const props = { ...defaultProps, showSettingsModal: true }

    it('renders the settings modal with theme option, model input and reset option', () => {
      render(<AccountModals {...props} />)
      expect(screen.getByText('Paramètres')).toBeInTheDocument()
      expect(screen.getByText('Thème')).toBeInTheDocument()
      expect(screen.getByText('Modèle IA')).toBeInTheDocument()
      expect(screen.getByDisplayValue('llama3.2 (Local Ollama)')).toBeInTheDocument()
      expect(screen.getByText('Données de l\'application')).toBeInTheDocument()
    })

    it('shows "Mode Clair" if darkMode is true, otherwise "Mode Sombre"', () => {
      const { rerender } = render(<AccountModals {...props} darkMode={false} />)
      expect(screen.getByRole('button', { name: 'Mode Sombre' })).toBeInTheDocument()

      rerender(<AccountModals {...props} darkMode={true} />)
      expect(screen.getByRole('button', { name: 'Mode Clair' })).toBeInTheDocument()
    })

    it('calls setDarkMode when changing the theme', () => {
      render(<AccountModals {...props} />)
      const themeBtn = screen.getByRole('button', { name: 'Mode Sombre' })
      fireEvent.click(themeBtn)
      expect(props.setDarkMode).toHaveBeenCalled()
    })

    it('clears localStorage and reloads the window on confirmation of reset', () => {
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
      const clearSpy = vi.spyOn(Storage.prototype, 'clear')
      const setItemSpy = vi.spyOn(Storage.prototype, 'setItem')

      localStorage.setItem('theme', 'dark')
      localStorage.setItem('lastLogin', '2026-07-16')
      localStorage.setItem('lang', 'fr')

      render(<AccountModals {...props} />)
      const resetBtn = screen.getByRole('button', { name: 'Réinitialiser' })
      fireEvent.click(resetBtn)

      expect(confirmSpy).toHaveBeenCalled()
      expect(clearSpy).toHaveBeenCalled()
      expect(setItemSpy).toHaveBeenCalledWith('theme', 'dark')
      expect(setItemSpy).toHaveBeenCalledWith('lastLogin', '2026-07-16')
      expect(setItemSpy).toHaveBeenCalledWith('lang', 'fr')
      expect(window.location.reload).toHaveBeenCalled()
    })

    it('does not reset data if confirmation is cancelled', () => {
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
      const clearSpy = vi.spyOn(Storage.prototype, 'clear')

      render(<AccountModals {...props} />)
      const resetBtn = screen.getByRole('button', { name: 'Réinitialiser' })
      fireEvent.click(resetBtn)

      expect(confirmSpy).toHaveBeenCalled()
      expect(clearSpy).not.toHaveBeenCalled()
      expect(window.location.reload).not.toHaveBeenCalled()
    })

    it('calls setShowSettingsModal(false) when clicking close button', () => {
      render(<AccountModals {...props} />)
      const closeBtn = document.querySelector('.modal-close-btn')
      expect(closeBtn).toBeInTheDocument()
      fireEvent.click(closeBtn)
      expect(props.setShowSettingsModal).toHaveBeenCalledWith(false)
    })
  })

  // ── Tests du Listener Clavier Global ─────────────────────────────────────
  describe('Global Keyboard Event Listener', () => {
    it('closes all modals when Escape is pressed', () => {
      const props = {
        ...defaultProps,
        showAccountModal: true,
        showSettingsModal: false,
      }
      render(<AccountModals {...props} />)

      fireEvent.keyDown(window, { key: 'Escape' })

      expect(props.setShowAccountModal).toHaveBeenCalledWith(false)
      expect(props.setShowSettingsModal).toHaveBeenCalledWith(false)
    })
  })
})
