import type { User } from 'oidc-client-ts'
import { config } from './config'

export type LinkStatus = 'active' | 'disabled' | 'expired' | 'exhausted'
export type ManagedLink = {
  id: number
  short_code: string
  shortened_url: string
  original_url: string
  title: string | null
  created_at: string
  expires_at: string | null
  visit_count: number
  max_visits: number | null
  status: LinkStatus
  policy_type: 'public' | 'password_protected' | 'ip_restricted'
}
export type LinkList = { items: ManagedLink[]; total: number }
export type CreateLink = { url: string; ttl_seconds: number; short_code?: string }

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

export async function api<T>(user: User, path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${user.access_token}`,
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new ApiError(response.status, body.detail || `Request failed (${response.status})`)
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}
