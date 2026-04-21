const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('ghost_token')
}

export function setToken(token: string) {
  localStorage.setItem('ghost_token', token)
  // Mirror to cookie so Next.js middleware can gate routes server-side
  document.cookie = `ghost_token=${token}; path=/; SameSite=Lax`
}

export function clearToken() {
  localStorage.removeItem('ghost_token')
  localStorage.removeItem('ghost_account_id')
  document.cookie = 'ghost_token=; path=/; max-age=0'
}

export function getAccountId(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('ghost_account_id')
}

export function setAccountId(id: string) {
  localStorage.setItem('ghost_account_id', id)
}

async function request(path: string, opts: RequestInit = {}): Promise<any> {
  const token = getToken()
  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...((opts.headers as Record<string, string>) || {}),
    },
  })
  if (res.status === 401) {
    clearToken()
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || data.message || 'Request failed')
  return data
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string, name?: string) =>
    request('/auth/register', { method: 'POST', body: JSON.stringify({ email, password, name }) }),
  me: () => request('/auth/me'),

  // Accounts
  getAccounts: () => request('/accounts'),
  createAccount: () => request('/accounts', { method: 'POST' }),
  connectLinkedIn: (accountId: string) =>
    request(`/accounts/${accountId}/connect-linkedin`, { method: 'POST' }),
  updateSession: (accountId: string, liAt: string, jsessionId: string) =>
    request(`/accounts/${accountId}/session`, {
      method: 'PUT',
      body: JSON.stringify({ liAt, jsessionId }),
    }),
  getAccountStats: (accountId: string) => request(`/stats?account_id=${accountId}`),

  // Campaigns
  getCampaigns: () => request('/campaigns'),
  createCampaign: (data: Record<string, unknown>) =>
    request('/campaigns', { method: 'POST', body: JSON.stringify(data) }),
  getCampaign: (id: string) => request(`/campaigns/${id}`),
  updateCampaignStatus: (id: string, status: string) =>
    request(`/campaigns/${id}/status`, { method: 'PUT', body: JSON.stringify({ status }) }),
  deleteCampaign: (id: string) =>
    request(`/campaigns/${id}`, { method: 'DELETE' }),

  // Prospects
  getProspects: (campaignId: string, limit = 50, offset = 0) =>
    request(`/campaigns/${campaignId}/prospects?limit=${limit}&offset=${offset}`),
  addProspect: (campaignId: string, data: Record<string, unknown>) =>
    request(`/campaigns/${campaignId}/prospects`, { method: 'POST', body: JSON.stringify(data) }),
  uploadProspects: (campaignId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    const token = getToken()
    return fetch(`${API_BASE}/campaigns/${campaignId}/prospects/upload`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    }).then(r => r.json())
  },

  // Queue
  getQueue: (accountId: string) => request(`/queue?account_id=${accountId}`),
  approveMessage: (id: string, editedContent?: string) =>
    request(`/queue/${id}/approve`, { method: 'POST', body: JSON.stringify({ editedContent }) }),
  rejectMessage: (id: string) =>
    request(`/queue/${id}/reject`, { method: 'POST' }),
  bulkQueueAction: (accountId: string, action: 'approve' | 'reject') =>
    request('/queue/bulk', { method: 'POST', body: JSON.stringify({ action, account_id: accountId }) }),

  // Pipeline
  getPipeline: (accountId: string) => request(`/pipeline?account_id=${accountId}`),

  // Agent
  startAgent: (accountId: string, options?: { continuous?: boolean; skipWarmup?: boolean; taskId?: string }) =>
    request('/agent/start', {
      method: 'POST',
      body: JSON.stringify({
        account_id: accountId,
        continuous: options?.continuous ?? true,
        skip_warmup: options?.skipWarmup ?? false,
        task_id: options?.taskId ?? null,
      }),
    }),
  stopAgent: (accountId: string) =>
    request('/agent/stop', { method: 'POST', body: JSON.stringify({ account_id: accountId }) }),
  getAgentStatus: (accountId: string) => request(`/agent/status/${accountId}`),

  // Tasks
  getTasks: () => request('/tasks'),
  createTask: (data: { linkedInAccountId: string; title: string; instruction: string }) =>
    request('/tasks', { method: 'POST', body: JSON.stringify(data) }),
  getTask: (id: string) => request(`/tasks/${id}`),
  runTask: (id: string) =>
    request(`/tasks/${id}/run`, { method: 'POST' }),
  deleteTask: (id: string) =>
    request(`/tasks/${id}`, { method: 'DELETE' }),
}

export function wsUrl(path: string): string {
  const base = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace('http', 'ws')
  return `${base}${path}`
}
