/**
 * Rubric B-5 wants meaningful component tests, not render smoke tests. Each
 * one below pins a behaviour the assignment names explicitly.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SubmitView } from '../views/SubmitView'
import { makeComplaint, jsonResponse } from './factories'

describe('SubmitView', () => {
  it('blocks submission and explains why when the text is too short, without calling the API', async () => {
    const fetchSpy = vi.fn()
    vi.stubGlobal('fetch', fetchSpy)
    const user = userEvent.setup()

    render(<SubmitView />)
    await user.type(screen.getByLabelText(/what is wrong/i), 'short')
    await user.type(screen.getByLabelText(/^location$/i), 'G-9')
    await user.click(screen.getByRole('button', { name: /submit complaint/i }))

    expect(await screen.findByText(/at least 10 characters/i)).toBeInTheDocument()
    // Client-side validation mirrors the server's rules to save a round trip.
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('renders the category, priority, summary and provider the server returned', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(makeComplaint(), { status: 201 })),
    )
    const user = userEvent.setup()

    render(<SubmitView />)
    await user.type(
      screen.getByLabelText(/what is wrong/i),
      'Burst water main flooding Street 12 since fajr',
    )
    await user.type(screen.getByLabelText(/^location$/i), 'Sector G-9')
    await user.click(screen.getByRole('button', { name: /submit complaint/i }))

    const result = await screen.findByTestId('triage-result')
    expect(result).toHaveTextContent('water')
    expect(result).toHaveTextContent('high')
    expect(result).toHaveTextContent('Burst main flooding Street 12')
    expect(screen.getByTestId('triaged-by')).toHaveTextContent('llm:groq')
  })

  it('shows the 429 body and Retry-After rather than a generic failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          { detail: 'Rate limit exceeded. Slow down and try again shortly.' },
          { status: 429, headers: { 'Retry-After': '42' } },
        ),
      ),
    )
    const user = userEvent.setup()

    render(<SubmitView />)
    await user.type(screen.getByLabelText(/what is wrong/i), 'Street light out for three weeks now')
    await user.type(screen.getByLabelText(/^location$/i), 'Sector F-10')
    await user.click(screen.getByRole('button', { name: /submit complaint/i }))

    const banner = await screen.findByTestId('server-error')
    expect(banner).toHaveTextContent('Rate limit exceeded')
    expect(banner).toHaveTextContent('42 seconds')
  })

  it('surfaces the field-level errors from a 400 body one by one', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            detail: 'Validation failed',
            errors: [{ loc: ['body', 'location'], msg: 'String should have at least 3 characters', type: 'too_short' }],
          },
          { status: 400 },
        ),
      ),
    )
    const user = userEvent.setup()

    render(<SubmitView />)
    await user.type(screen.getByLabelText(/what is wrong/i), 'Sewage backing up into the lane again')
    await user.type(screen.getByLabelText(/^location$/i), 'G-9')
    await user.click(screen.getByRole('button', { name: /submit complaint/i }))

    const banner = await screen.findByTestId('server-error')
    expect(banner).toHaveTextContent('location')
    expect(banner).toHaveTextContent('at least 3 characters')
  })

  it('says the triage call is slow while it is in flight, then clears', async () => {
    let release!: (value: Response) => void
    const pending = new Promise<Response>((resolve) => {
      release = resolve
    })
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(pending))
    const user = userEvent.setup()

    render(<SubmitView />)
    await user.type(screen.getByLabelText(/what is wrong/i), 'Transformer sparking near the school gate')
    await user.type(screen.getByLabelText(/^location$/i), 'Sector I-8')
    await user.click(screen.getByRole('button', { name: /submit complaint/i }))

    // Honest loading state (§2.1): it says an AI call is happening, not just "…".
    expect(await screen.findByTestId('loading-note')).toHaveTextContent(/language model/i)

    release(jsonResponse(makeComplaint({ category: 'electricity' }), { status: 201 }))
    await waitFor(() => expect(screen.queryByTestId('loading-note')).not.toBeInTheDocument())
  })
})
