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
export type CreateLink = {
  url: string
  ttl_seconds: number
  short_code?: string
  title?: string
  max_visits?: number
  policy: { type: 'public' } | { type: 'password_protected'; password: string } | { type: 'ip_restricted'; ip_list: string[] }
}

function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map(item => {
      if (typeof item === 'string') return item
      if (item && typeof item === 'object' && 'msg' in item) {
        const location = 'loc' in item && Array.isArray(item.loc) ? item.loc.slice(1).join('.') : ''
        return `${location ? `${location}: ` : ''}${String(item.msg)}`
      }
      return 'Invalid request'
    }).join('; ')
  }
  if (detail && typeof detail === 'object' && 'message' in detail) return String(detail.message)
  return `Request failed (${status})`
}

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
    throw new ApiError(response.status, errorMessage(body.detail, response.status))
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}
