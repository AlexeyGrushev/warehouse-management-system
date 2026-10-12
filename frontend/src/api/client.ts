const TOKEN_KEY = 'wms_token'

let token: string | null = null
let onUnauthorized: (() => void) | null = null

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, detail: string) {
    super(detail)
    this.status = status
    this.code = code
  }
}

export function getToken(): string | null {
  if (token === null) {
    token = sessionStorage.getItem(TOKEN_KEY)
  }
  return token
}

export function setToken(value: string | null): void {
  token = value
  if (value === null) {
    sessionStorage.removeItem(TOKEN_KEY)
  } else {
    sessionStorage.setItem(TOKEN_KEY, value)
  }
}

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }
  const current = getToken()
  if (current !== null) {
    headers.set('Authorization', `Bearer ${current}`)
  }

  const response = await fetch(`/api/v1${path}`, { ...init, headers })
  if (response.ok) {
    return (response.status === 204 ? undefined : await response.json()) as T
  }

  const body = await response.json().catch(() => ({}))
  // 401 на любом запросе, кроме самого логина, означает «токен больше не годится»
  if (response.status === 401 && current !== null) {
    setToken(null)
    onUnauthorized?.()
  }
  throw new ApiError(
    response.status,
    body.code ?? 'ERROR',
    body.detail ?? `Ошибка запроса (${response.status})`,
  )
}
