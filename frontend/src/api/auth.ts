import { apiFetch } from './client'
import type { TokenResponse, User } from './types'

export function login(email: string, password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export function fetchMe(): Promise<User> {
  return apiFetch<User>('/users/me')
}
