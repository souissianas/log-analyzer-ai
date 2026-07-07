import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Dashboard from './Dashboard'
import * as api from '../api'
import { LanguageProvider } from '../i18n'

// Mock the API module
vi.mock('../api', () => ({
  fetchDashboardStats: vi.fn(),
}))

const mockStats = {
  total_analyses: 12,
  total_errors: 45,
  total_analyzed: 10,
  errors_by_level: {
    ERROR: 30,
    CRITICAL: 5,
    WARNING: 10,
  },
  analyses_per_day: [
    { day: '2026-06-18', count: 5, errors: 20 },
    { day: '2026-06-19', count: 7, errors: 25 },
  ],
  top_files: [
    { filename: 'syslog.log', runs: 8, total_errors: 35 },
    { filename: 'nginx.log', runs: 4, total_errors: 10 },
  ],
  errors_by_category: [
    { category: 'Network', count: 18 },
    { category: 'Database', count: 17 },
  ],
}

describe('Dashboard Component', () => {
  it('renders loading spinner initially', async () => {
    // Return a promise that doesn't resolve immediately to test loading state
    api.fetchDashboardStats.mockReturnValue(new Promise(() => {}))

    render(
      <LanguageProvider>
        <Dashboard onClose={vi.fn()} />
      </LanguageProvider>
    )

    expect(screen.getByText(/Chargement des statistiques/i)).toBeInTheDocument()
  })

  it('renders stats successfully after API resolve', async () => {
    api.fetchDashboardStats.mockResolvedValue(mockStats)

    render(
      <LanguageProvider>
        <Dashboard onClose={vi.fn()} />
      </LanguageProvider>
    )

    // Wait for the loader to disappear and stats to load
    await waitFor(() => {
      expect(screen.queryByText(/Chargement des statistiques/i)).not.toBeInTheDocument()
    })

    // Check KPI Cards
    expect(screen.getByText('12')).toBeInTheDocument() // total_analyses
    expect(screen.getByText('45')).toBeInTheDocument() // total_errors
    // In Dashboard.jsx it calculates: Math.round((stats.total_analyzed / stats.total_errors) * 100) -> (10/45)*100 = 22%
    expect(screen.getByText('22%')).toBeInTheDocument()

    // Check titles
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText("Vue d'ensemble de vos analyses de logs")).toBeInTheDocument()

    // Check files and levels
    expect(screen.getByText(/syslog.log/i)).toBeInTheDocument()
    expect(screen.getByText(/nginx.log/i)).toBeInTheDocument()
    expect(screen.getByText('CRITICAL')).toBeInTheDocument()
    expect(screen.getAllByText('5').length).toBeGreaterThan(0)
  })

  it('renders error message when API fails', async () => {
    api.fetchDashboardStats.mockRejectedValue(new Error('Erreur de connexion API'))

    render(
      <LanguageProvider>
        <Dashboard onClose={vi.fn()} />
      </LanguageProvider>
    )

    await waitFor(() => {
      expect(screen.getByText(/Erreur de connexion API/i)).toBeInTheDocument()
    })
  })
})
