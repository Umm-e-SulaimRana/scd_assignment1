import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DashboardView } from '../views/DashboardView'
import { makeComplaint, jsonResponse } from './factories'

function listResponse(total: number, page = 1) {
  return jsonResponse({
    items: [makeComplaint({ status: 'resolved' })],
    total,
    page,
    page_size: 10,
  })
}

describe('DashboardView', () => {
  it("renders the server's 409 message verbatim instead of a generic error", async () => {
    const fetchSpy = vi
      .fn()
      .mockResolvedValueOnce(listResponse(1))
      .mockResolvedValueOnce(
        jsonResponse({ detail: 'Cannot transition from resolved to open' }, { status: 409 }),
      )
    vi.stubGlobal('fetch', fetchSpy)
    const user = userEvent.setup()

    render(<DashboardView />)
    await screen.findByTestId('complaint-row')
    await user.click(screen.getByRole('button', { name: 'open' }))

    // The whole point: the message names the attempted transition.
    expect(await screen.findByTestId('transition-error')).toHaveTextContent(
      'Cannot transition from resolved to open',
    )
  })

  it('sends the chosen filters as query parameters and resets to page 1', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(listResponse(40))
    vi.stubGlobal('fetch', fetchSpy)
    const user = userEvent.setup()

    render(<DashboardView />)
    await screen.findByTestId('complaint-row')

    await user.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => expect(screen.getByTestId('page-indicator')).toHaveTextContent('Page 2'))

    await user.selectOptions(screen.getByLabelText(/category/i), 'water')

    await waitFor(() => {
      const lastUrl = String(fetchSpy.mock.calls[fetchSpy.mock.calls.length - 1][0])
      expect(lastUrl).toContain('category=water')
      expect(lastUrl).toContain('page=1')
    })
    expect(screen.getByTestId('page-indicator')).toHaveTextContent('Page 1')
  })

  it('paginates from the total the server reports, not from the rows on screen', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(listResponse(23)))

    render(<DashboardView />)
    // 23 complaints at page_size 10 is three pages, from one row of data.
    expect(await screen.findByTestId('page-indicator')).toHaveTextContent('Page 1 of 3')
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled()
  })
})
