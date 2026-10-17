import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RequireAuth } from './RequireAuth'
import { Links } from './pages/Links'
import { ManageLink } from './pages/ManageLink'

const auth = vi.hoisted(() => ({ user: null as object | null, loading: false }))
vi.mock('./AuthContext', () => ({ useAuth: () => auth }))
vi.mock('./auth', () => ({ signIn: vi.fn(), signOut: vi.fn() }))

function renderPage(path: string, component: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes><Route path="/" element={<p>sign in page</p>} /><Route path="/links" element={component} /><Route path="/links/:id" element={component} /></Routes></MemoryRouter></QueryClientProvider>)
}

beforeEach(() => {
  auth.user = { access_token: 'test-token', profile: { sub: 'user-1' } }
})

describe('protected routes', () => {
  it('returns signed-out users to sign in', () => {
    auth.user = null
    renderPage('/links', <RequireAuth><p>private links</p></RequireAuth>)
    expect(screen.getByText('sign in page')).toBeInTheDocument()
    expect(screen.queryByText('private links')).not.toBeInTheDocument()
  })
})

describe('create link', () => {
  it('rejects non-HTTP destinations before sending a request', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
    renderPage('/links', <Links />)
    await screen.findByText('No links yet. Create your first one above.')
    fireEvent.change(screen.getByLabelText('long url'), { target: { value: 'ftp://example.com' } })
    fireEvent.click(screen.getByRole('button', { name: 'shorten >' }))
    expect(screen.getByRole('alert')).toHaveTextContent('http:// or https://')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

describe('disable link', () => {
  it('requires confirmation before sending DELETE', async () => {
    const link = { id: 1, short_code: 'abc', shortened_url: 'http://localhost:8080/link/abc', original_url: 'https://example.com', title: null, created_at: '2026-10-17T00:00:00Z', expires_at: '2026-10-18T00:00:00Z', visit_count: 0, max_visits: null, status: 'active', policy_type: 'public' }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, init) => init?.method === 'DELETE' ? new Response(null, { status: 204 }) : new Response(JSON.stringify(link), { status: 200 }))
    renderPage('/links/abc', <ManageLink />)
    await screen.findByRole('button', { name: 'disable link' })
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'DELETE')).toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: 'disable link' }))
    expect(screen.getByText('Visitors will no longer be redirected. This cannot be undone.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'yes, disable' }))
    await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'DELETE')).toHaveLength(1))
  })
})
