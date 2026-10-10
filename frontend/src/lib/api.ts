const TOKEN_KEY = 'access_token'

export interface User {
  id: string
  username: string
  created_at: string
}

export interface Token {
  access_token: string
  token_type: string
}

export interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface Message {
  role: string
  content: string
}

export interface HistoryResponse {
  conversation_id: string
  history: Message[]
}

export interface TurnResponse {
  conversation_id: string
  history: Message[]
  paused: boolean
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function saveToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

async function request<T>(path: string, options: { method?: string; body?: string } = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(path, { method: options.method ?? 'GET', headers, body: options.body })
  if (res.status === 204) return undefined as T

  let data: unknown = null
  try {
    data = await res.json()
  } catch {
    data = null
  }

  if (!res.ok) {
    const detail = (data as { detail?: string } | null)?.detail ?? `请求失败 (${res.status})`
    throw new ApiError(res.status, detail)
  }
  return data as T
}

export const api = {
  register: (username: string, password: string) =>
    request<User>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  login: (username: string, password: string) =>
    request<Token>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  me: () => request<User>('/api/auth/me'),

  listConversations: () => request<Conversation[]>('/api/conversations'),

  createConversation: (title = '新会话') =>
    request<Conversation>('/api/conversations', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),

  getHistory: (id: string) => request<HistoryResponse>(`/api/conversations/${id}/history`),

  runTurn: (id: string, message: string, successCriteria = '') =>
    request<TurnResponse>(`/api/conversations/${id}/turn`, {
      method: 'POST',
      body: JSON.stringify({ message, success_criteria: successCriteria }),
    }),

  approve: (id: string) =>
    request<TurnResponse>(`/api/conversations/${id}/approve`, { method: 'POST' }),

  deleteConversation: (id: string) =>
    request<void>(`/api/conversations/${id}`, { method: 'DELETE' }),
}