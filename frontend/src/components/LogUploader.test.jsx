import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import LogUploader from '../components/LogUploader'
import { LanguageProvider } from '../i18n'

describe('LogUploader', () => {
  it('rejects unsupported file extensions', () => {
    const onAnalyze = vi.fn()
    render(
      <LanguageProvider>
        <LogUploader onAnalyze={onAnalyze} disabled={false} />
      </LanguageProvider>
    )

    const input = document.getElementById('log-file')

    fireEvent.change(input, {
      target: { files: [new File(['2026-06-18 ERROR fail'], 'report.csv', { type: 'text/csv' })] },
    })

    expect(screen.getByText(/Format non supporté/i)).toBeInTheDocument()
    expect(onAnalyze).not.toHaveBeenCalled()
  })

  it('accepts log files and triggers analyze callback', () => {
    const onAnalyze = vi.fn()
    render(
      <LanguageProvider>
        <LogUploader onAnalyze={onAnalyze} disabled={false} />
      </LanguageProvider>
    )

    const input = document.getElementById('log-file')
    const file = new File(['2026-06-18 10:00:00 ERROR timeout'], 'app.log', { type: 'text/plain' })

    fireEvent.change(input, { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: /Analyser avec IA/i }))

    expect(onAnalyze).toHaveBeenCalledWith(file)
  })
})
