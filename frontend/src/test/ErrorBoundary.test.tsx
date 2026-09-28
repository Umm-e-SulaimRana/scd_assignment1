import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ErrorBoundary } from '../components/ErrorBoundary'

function Explodes() {
  throw new Error('render blew up')
  return null
}

describe('ErrorBoundary', () => {
  it('replaces a crashed subtree with a named panel instead of a blank page', () => {
    // React logs the caught error itself; silence it so the run stays readable.
    vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <ErrorBoundary label="the operations dashboard">
        <Explodes />
      </ErrorBoundary>,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('the operations dashboard')
    expect(screen.getByText('render blew up')).toBeInTheDocument()
  })

  it('renders its children untouched when nothing throws', () => {
    render(
      <ErrorBoundary>
        <p>all fine</p>
      </ErrorBoundary>,
    )
    expect(screen.getByText('all fine')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
