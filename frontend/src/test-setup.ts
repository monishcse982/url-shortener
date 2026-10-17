import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8080')
vi.stubEnv('VITE_COGNITO_ISSUER', 'https://cognito-idp.example.test/pool')
vi.stubEnv('VITE_COGNITO_CLIENT_ID', 'test-client')
vi.stubEnv('VITE_COGNITO_DOMAIN', 'https://login.example.test')
vi.stubEnv('VITE_COGNITO_REDIRECT_URI', 'http://localhost:5173/auth/callback')
vi.stubEnv('VITE_COGNITO_LOGOUT_URI', 'http://localhost:5173/')
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })),
})
window.requestAnimationFrame = callback => window.setTimeout(callback, 0)

afterEach(() => { cleanup(); vi.restoreAllMocks() })
