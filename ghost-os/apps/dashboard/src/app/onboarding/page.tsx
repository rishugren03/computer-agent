'use client'

import { useState, useEffect, useRef } from 'react'
import { api, setAccountId, getAccountId, wsUrl } from '../../lib/api'

interface Account {
  id: string
  sessionStatus: string
  warmupStatus: string
  agentStatus: string
  linkedInName?: string
}

interface Campaign {
  id: string
  name: string
  status: string
}

const STEPS = [
  { id: 'account', title: 'Connect LinkedIn', description: 'Link your LinkedIn account' },
  { id: 'warmup', title: 'Warmup Phase', description: 'Build account trust safely' },
  { id: 'campaign', title: 'Create Campaign', description: 'Define your outreach goal' },
  { id: 'prospects', title: 'Add Prospects', description: 'Upload your target list' },
  { id: 'launch', title: 'Launch Agent', description: 'Start automated outreach' },
]

function StepIndicator({ current, steps }: { current: number; steps: typeof STEPS }) {
  return (
    <div className="flex items-center gap-2 mb-10">
      {steps.map((step, i) => (
        <div key={step.id} className="flex items-center gap-2">
          <div className={`flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold border-2 transition-all ${
            i < current
              ? 'bg-emerald-500 border-emerald-500 text-white'
              : i === current
              ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400'
              : 'bg-slate-800 border-slate-700 text-slate-500'
          }`}>
            {i < current ? (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              i + 1
            )}
          </div>
          {i < steps.length - 1 && (
            <div className={`h-0.5 w-8 sm:w-16 transition-all ${i < current ? 'bg-emerald-500' : 'bg-slate-700'}`} />
          )}
        </div>
      ))}
    </div>
  )
}

// ─── Step 1: Connect LinkedIn ─────────────────────────────────────────────────

function StepAccount({
  onDone,
}: {
  onDone: (account: Account) => void
}) {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [creating, setCreating] = useState(false)
  const [tab, setTab] = useState<'cookie' | 'browser'>('cookie')

  // Cookie paste state
  const [liAt, setLiAt] = useState('')
  const [saving, setSaving] = useState(false)

  // Browser login state
  const [connecting, setConnecting] = useState(false)
  const [liveStream, setLiveStream] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const accountId = getAccountId()

  useEffect(() => {
    api.getAccounts().then((accs: Account[]) => {
      setAccounts(accs)
      const connected = accs.find(a => a.sessionStatus === 'CONNECTED')
      if (connected) {
        setAccountId(connected.id)
        onDone(connected)
      } else if (accs.length > 0) {
        setAccountId(accs[0].id)
      }
    })
  }, [])

  // WebSocket for live view (browser tab only)
  useEffect(() => {
    if (tab !== 'browser' || !accountId) return
    const url = wsUrl(`/ws/live/${accountId}`)
    const ws = new WebSocket(url)
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === 'screen') setLiveStream(`data:image/jpeg;base64,${msg.data}`)
      } catch {}
    }
    ws.onerror = () => ws.close()
    wsRef.current = ws
    return () => { ws.close(); wsRef.current = null }
  }, [tab, accountId])

  const handleCreate = async () => {
    setCreating(true)
    try {
      const acc = await api.createAccount()
      setAccounts([acc])
      setAccountId(acc.id)
    } catch (e: any) {
      alert(e.message)
    } finally {
      setCreating(false)
    }
  }

  const handleCookieSave = async () => {
    if (!accountId || !liAt.trim()) return
    setSaving(true)
    try {
      await api.updateSession(accountId, liAt.trim(), '')
      const accs: Account[] = await api.getAccounts()
      setAccounts(accs)
      const acc = accs.find(a => a.id === accountId)
      if (acc) onDone(acc)
    } catch (e: any) {
      alert('Failed to save session: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleConnect = async () => {
    if (!accountId) return
    setConnecting(true)
    try {
      await api.connectLinkedIn(accountId)
    } catch (e: any) {
      alert(e.message)
    } finally {
      setConnecting(false)
    }
  }

  const handlePollStatus = async () => {
    if (!accountId) return
    const accs: Account[] = await api.getAccounts()
    setAccounts(accs)
    const acc = accs.find(a => a.id === accountId)
    if (acc?.sessionStatus === 'CONNECTED') {
      onDone(acc)
    } else {
      alert("LinkedIn session not detected yet. Please complete the login in the live view below.")
    }
  }

  const selectedAccount = accounts.find(a => a.id === accountId)

  if (accounts.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-bold text-slate-100 mb-1">Connect your LinkedIn account</h2>
          <p className="text-slate-400 text-sm">We'll use your account to send personalized outreach messages.</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center">
          <div className="w-14 h-14 rounded-full bg-indigo-500/20 flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          <p className="text-slate-300 font-medium mb-1">No accounts added yet</p>
          <p className="text-slate-500 text-sm mb-5">Add a LinkedIn account to get started</p>
          <button
            onClick={handleCreate}
            disabled={creating}
            className="px-6 py-2.5 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 rounded-lg text-sm font-semibold transition-colors"
          >
            {creating ? 'Creating...' : 'Add LinkedIn Account'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-100 mb-1">Connect your LinkedIn account</h2>
        <p className="text-slate-400 text-sm">Choose how you want to authenticate.</p>
      </div>

      {/* Account row */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-indigo-500/20 flex items-center justify-center text-sm font-bold text-indigo-400">
          {selectedAccount?.linkedInName?.[0] || 'LI'}
        </div>
        <div>
          <p className="text-sm font-medium text-slate-200">{selectedAccount?.linkedInName || 'LinkedIn Account'}</p>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className={`w-1.5 h-1.5 rounded-full ${selectedAccount?.sessionStatus === 'CONNECTED' ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
            <span className="text-xs text-slate-400">
              {selectedAccount?.sessionStatus === 'CONNECTED' ? 'Connected' : 'Not connected'}
            </span>
          </div>
        </div>
      </div>

      {/* Tab toggle */}
      <div className="flex gap-1 p-1 bg-slate-900 border border-slate-800 rounded-xl">
        <button
          onClick={() => setTab('cookie')}
          className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors ${tab === 'cookie' ? 'bg-emerald-500 text-white' : 'text-slate-400 hover:text-slate-200'}`}
        >
          Paste Cookie (fast)
        </button>
        <button
          onClick={() => setTab('browser')}
          className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors ${tab === 'browser' ? 'bg-slate-700 text-slate-100' : 'text-slate-400 hover:text-slate-200'}`}
        >
          Browser Login
        </button>
      </div>

      {tab === 'cookie' ? (
        <div className="space-y-4">
          {/* Instructions */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-2 text-sm">
            <p className="text-slate-300 font-medium">How to get your session cookie:</p>
            <ol className="list-decimal list-inside space-y-1.5 text-slate-400">
              <li>Open Chrome and go to <span className="text-slate-300 font-mono">linkedin.com</span> (make sure you're logged in)</li>
              <li>Press <span className="font-mono text-slate-200 bg-slate-800 px-1.5 py-0.5 rounded text-xs">F12</span> to open DevTools</li>
              <li>Go to <span className="text-slate-200">Application</span> → <span className="text-slate-200">Storage</span> → <span className="text-slate-200">Cookies</span> → <span className="text-slate-200">https://www.linkedin.com</span></li>
              <li>Find the cookie named <span className="font-mono text-emerald-400 bg-slate-800 px-1.5 py-0.5 rounded text-xs">li_at</span> and copy its value</li>
            </ol>
          </div>

          <div>
            <label className="text-xs text-slate-400 block mb-1.5">
              li_at cookie value
            </label>
            <input
              type="password"
              value={liAt}
              onChange={e => setLiAt(e.target.value)}
              placeholder="Paste your li_at value here..."
              className="w-full bg-slate-950 border border-slate-700 focus:border-emerald-500 rounded-lg px-3 py-2.5 text-sm text-slate-200 font-mono outline-none transition-colors"
            />
            <p className="text-xs text-slate-600 mt-1">Stored encrypted. We only use this to operate LinkedIn on your behalf.</p>
          </div>

          <button
            onClick={handleCookieSave}
            disabled={saving || !liAt.trim()}
            className="w-full py-3 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 rounded-xl text-sm font-semibold transition-colors"
          >
            {saving ? 'Connecting...' : 'Connect LinkedIn →'}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={handleConnect}
              disabled={connecting}
              className="px-4 py-2 text-sm text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 hover:bg-indigo-500/20 rounded-lg transition-colors disabled:opacity-50"
            >
              {connecting ? 'Starting browser...' : 'Open Login Browser'}
            </button>
          </div>

          <div className="bg-black rounded-xl border border-slate-800 overflow-hidden aspect-video flex items-center justify-center">
            {liveStream ? (
              <img src={liveStream} alt="Browser" className="w-full h-full object-fill" />
            ) : (
              <div className="text-center">
                <div className="w-12 h-12 rounded-full bg-slate-900 flex items-center justify-center mx-auto mb-3">
                  <svg className="w-6 h-6 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </div>
                <p className="text-slate-600 text-sm">Click "Open Login Browser" to see the live view</p>
              </div>
            )}
          </div>

          <button
            onClick={handlePollStatus}
            className="w-full py-3 bg-emerald-500 hover:bg-emerald-400 rounded-xl text-sm font-semibold transition-colors"
          >
            I've completed the LinkedIn login →
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Step 2: Warmup ───────────────────────────────────────────────────────────

function StepWarmup({
  account,
  launching,
  onDone,
}: {
  account: Account
  launching?: boolean
  onDone: (skipWarmup: boolean) => void
}) {
  const [choice, setChoice] = useState<'warmup' | 'skip' | null>(null)

  if (account.warmupStatus === 'COMPLETED') {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-bold text-slate-100 mb-1">Warmup already complete</h2>
          <p className="text-slate-400 text-sm">Your account has already completed the warmup phase. Ready for outreach.</p>
        </div>
        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-5 flex items-center gap-3">
          <svg className="w-6 h-6 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-emerald-400 font-medium text-sm">Account warmup completed — outreach is unlocked</p>
        </div>
        <button
          onClick={() => onDone(false)}
          className="w-full py-3 bg-emerald-500 hover:bg-emerald-400 rounded-xl text-sm font-semibold transition-colors"
        >
          Continue to Campaign Setup →
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-100 mb-1">Warmup phase</h2>
        <p className="text-slate-400 text-sm">Build account trust before running automated outreach.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <button
          onClick={() => setChoice('warmup')}
          className={`text-left p-5 rounded-xl border-2 transition-all ${
            choice === 'warmup'
              ? 'border-emerald-500 bg-emerald-500/10'
              : 'border-slate-700 bg-slate-900 hover:border-slate-600'
          }`}
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="text-2xl">🔥</span>
            <span className="font-semibold text-slate-100">Run 48h Warmup</span>
          </div>
          <p className="text-sm text-slate-400">
            Agent does organic activity (likes, profile views) for 48 hours before sending any connection requests. Lowest detection risk.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full">Safest</span>
            <span className="text-xs bg-slate-700 text-slate-400 px-2 py-0.5 rounded-full">48h delay</span>
          </div>
        </button>

        <button
          onClick={() => setChoice('skip')}
          className={`text-left p-5 rounded-xl border-2 transition-all ${
            choice === 'skip'
              ? 'border-amber-500 bg-amber-500/10'
              : 'border-slate-700 bg-slate-900 hover:border-slate-600'
          }`}
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="text-2xl">⚡</span>
            <span className="font-semibold text-slate-100">Skip Warmup</span>
          </div>
          <p className="text-sm text-slate-400">
            Start sending connection requests immediately. Higher detection risk on fresh accounts. Recommended for accounts with existing activity.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="text-xs bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full">Higher risk</span>
            <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full">Instant start</span>
          </div>
        </button>
      </div>

      {choice === 'skip' && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 text-sm text-amber-400">
          <strong>Note:</strong> Skipping warmup on a fresh account increases the chance of LinkedIn's anti-spam detection. Use this only if your account already has significant activity history.
        </div>
      )}

      <button
        onClick={() => choice && onDone(choice === 'skip')}
        disabled={!choice || launching}
        className="w-full py-3 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 rounded-xl text-sm font-semibold transition-colors"
      >
        {launching ? 'Starting warmup...' : choice === 'skip' ? 'Skip Warmup & Continue →' : choice === 'warmup' ? 'Start 48h Warmup →' : 'Select an option above'}
      </button>
    </div>
  )
}

// ─── Step 3: Create Campaign ──────────────────────────────────────────────────

function StepCampaign({
  account,
  onDone,
}: {
  account: Account
  onDone: (campaign: Campaign) => void
}) {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [showForm, setShowForm] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({
    name: '',
    goal: '',
    personaTone: 'professional',
    dailyConnectionLimit: 15,
    autoApprove: false,
  })

  useEffect(() => {
    api.getCampaigns().then((cs: Campaign[]) => {
      setCampaigns(cs)
      if (cs.length > 0) setShowForm(false)
      else setShowForm(true)
    })
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      const campaign = await api.createCampaign({ ...form, linkedInAccountId: account.id })
      setCampaigns([campaign])
      setShowForm(false)
    } catch (err: any) {
      alert(err.message)
    } finally {
      setCreating(false)
    }
  }

  if (!showForm && campaigns.length > 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-bold text-slate-100 mb-1">Your campaigns</h2>
          <p className="text-slate-400 text-sm">Select a campaign or create a new one.</p>
        </div>
        <div className="space-y-3">
          {campaigns.map(c => (
            <button
              key={c.id}
              onClick={() => onDone(c)}
              className="w-full text-left bg-slate-900 border border-slate-700 hover:border-emerald-500/50 rounded-xl p-4 transition-colors"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-slate-100">{c.name}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full border ${
                  c.status === 'ACTIVE' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' :
                  'bg-slate-700/50 text-slate-400 border-slate-700'
                }`}>{c.status}</span>
              </div>
            </button>
          ))}
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="w-full py-2.5 text-sm text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/10 rounded-xl transition-colors"
        >
          + Create new campaign
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-100 mb-1">Create your campaign</h2>
        <p className="text-slate-400 text-sm">Define who you're targeting and what message you want to send.</p>
      </div>

      <form onSubmit={handleCreate} className="space-y-4">
        <div>
          <label className="text-xs text-slate-400 block mb-1.5">Campaign Name</label>
          <input
            required
            className="w-full bg-slate-950 border border-slate-700 focus:border-emerald-500 rounded-lg px-3 py-2.5 text-sm text-slate-200 outline-none transition-colors"
            placeholder="e.g. VP Sales Outreach Q2"
            value={form.name}
            onChange={e => setForm({ ...form, name: e.target.value })}
          />
        </div>
        <div>
          <label className="text-xs text-slate-400 block mb-1.5">Campaign Goal</label>
          <textarea
            required
            rows={3}
            className="w-full bg-slate-950 border border-slate-700 focus:border-emerald-500 rounded-lg px-3 py-2.5 text-sm text-slate-200 outline-none resize-none transition-colors"
            placeholder="e.g. Book a 15-minute demo call with VPs of Sales at B2B SaaS companies in the US"
            value={form.goal}
            onChange={e => setForm({ ...form, goal: e.target.value })}
          />
          <p className="text-xs text-slate-600 mt-1">The agent uses this to craft personalized messages.</p>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-slate-400 block mb-1.5">Message Tone</label>
            <select
              className="w-full bg-slate-950 border border-slate-700 focus:border-emerald-500 rounded-lg px-3 py-2.5 text-sm text-slate-200 outline-none"
              value={form.personaTone}
              onChange={e => setForm({ ...form, personaTone: e.target.value })}
            >
              <option value="professional">Professional</option>
              <option value="casual">Casual & Friendly</option>
              <option value="punchy">Short & Punchy</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1.5">Daily Connection Limit</label>
            <input
              type="number" min={1} max={25}
              className="w-full bg-slate-950 border border-slate-700 focus:border-emerald-500 rounded-lg px-3 py-2.5 text-sm text-slate-200 outline-none"
              value={form.dailyConnectionLimit}
              onChange={e => setForm({ ...form, dailyConnectionLimit: parseInt(e.target.value) })}
            />
          </div>
        </div>
        <label className="flex items-center gap-3 cursor-pointer select-none">
          <div
            onClick={() => setForm({ ...form, autoApprove: !form.autoApprove })}
            className={`w-10 h-5.5 rounded-full transition-colors relative ${form.autoApprove ? 'bg-amber-500' : 'bg-slate-700'}`}
          >
            <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${form.autoApprove ? 'translate-x-5' : 'translate-x-0.5'}`} />
          </div>
          <div>
            <p className="text-sm text-slate-300">Auto-send without review</p>
            <p className="text-xs text-slate-500">Messages are sent immediately without human approval</p>
          </div>
        </label>
        <button
          type="submit"
          disabled={creating}
          className="w-full py-3 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 rounded-xl text-sm font-semibold transition-colors"
        >
          {creating ? 'Creating...' : 'Create Campaign & Continue →'}
        </button>
      </form>
    </div>
  )
}

// ─── Step 4: Upload Prospects ─────────────────────────────────────────────────

function StepProspects({
  campaign,
  onDone,
}: {
  campaign: Campaign
  onDone: () => void
}) {
  const [uploading, setUploading] = useState(false)
  const [imported, setImported] = useState<number | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const result = await api.uploadProspects(campaign.id, file)
      setImported(result.imported || 0)
    } catch (err: any) {
      alert('Upload failed: ' + err.message)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-100 mb-1">Upload your prospect list</h2>
        <p className="text-slate-400 text-sm">Add the LinkedIn profiles you want to reach out to.</p>
      </div>

      {imported !== null ? (
        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-5">
          <div className="flex items-center gap-3">
            <svg className="w-6 h-6 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="text-emerald-400 font-semibold">{imported} prospects imported successfully</p>
              <p className="text-slate-400 text-xs mt-0.5">Campaign: {campaign.name}</p>
            </div>
          </div>
        </div>
      ) : (
        <div
          onClick={() => fileRef.current?.click()}
          className="bg-slate-900 border-2 border-dashed border-slate-700 hover:border-emerald-500/50 rounded-xl p-10 text-center cursor-pointer transition-colors"
        >
          <div className="w-14 h-14 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <p className="text-slate-300 font-medium mb-1">{uploading ? 'Uploading...' : 'Drop CSV or click to browse'}</p>
          <p className="text-slate-600 text-sm">Accepts columns: linkedInUrl, name, headline, company, notes</p>
          <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleFile} disabled={uploading} />
        </div>
      )}

      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <p className="text-xs text-slate-400 font-medium mb-2">CSV format example:</p>
        <pre className="text-xs text-slate-600 font-mono">linkedInUrl,name,headline,company
https://linkedin.com/in/johndoe,John Doe,VP Sales,Acme Corp</pre>
      </div>

      <div className="flex gap-3">
        <button
          onClick={onDone}
          className="flex-1 py-3 text-sm text-slate-400 border border-slate-700 hover:border-slate-600 rounded-xl transition-colors"
        >
          Skip for now — add later
        </button>
        {imported !== null && (
          <button
            onClick={onDone}
            className="flex-1 py-3 bg-emerald-500 hover:bg-emerald-400 rounded-xl text-sm font-semibold transition-colors"
          >
            Continue to Launch →
          </button>
        )}
      </div>
    </div>
  )
}

// ─── Step 5: Launch ───────────────────────────────────────────────────────────

function StepLaunch({
  account,
  campaign,
  skipWarmup,
  onDone,
}: {
  account: Account
  campaign: Campaign | null
  skipWarmup: boolean
  onDone: () => void
}) {
  const [launching, setLaunching] = useState(false)
  const [launched, setLaunched] = useState(false)
  const [mode, setMode] = useState<'full' | 'direct'>('full')

  const handleLaunch = async () => {
    setLaunching(true)
    try {
      await api.startAgent(account.id, {
        continuous: true,
        skipWarmup: skipWarmup || mode === 'direct',
      })
      setLaunched(true)
    } catch (err: any) {
      alert(err.message)
    } finally {
      setLaunching(false)
    }
  }

  if (launched) {
    return (
      <div className="space-y-6 text-center">
        <div className="w-16 h-16 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto">
          <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <div>
          <h2 className="text-2xl font-bold text-slate-100 mb-2">Agent is live!</h2>
          <p className="text-slate-400">GhostAgent is now running. Watch the live feed or check back later.</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <a href="/live"
            className="px-6 py-2.5 bg-emerald-500 hover:bg-emerald-400 rounded-xl text-sm font-semibold transition-colors text-center">
            Watch Live →
          </a>
          <a href="/"
            className="px-6 py-2.5 border border-slate-700 hover:border-slate-500 rounded-xl text-sm text-slate-300 transition-colors text-center">
            Go to Dashboard
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-100 mb-1">Launch the agent</h2>
        <p className="text-slate-400 text-sm">Review your configuration and start automated outreach.</p>
      </div>

      {/* Summary */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
        <h3 className="text-sm font-semibold text-slate-300">Configuration summary</h3>
        {[
          { label: 'LinkedIn Account', value: account.linkedInName || 'Connected', status: 'ok' },
          { label: 'Session', value: account.sessionStatus, status: account.sessionStatus === 'CONNECTED' ? 'ok' : 'warn' },
          { label: 'Warmup', value: skipWarmup ? 'Skipped' : account.warmupStatus === 'COMPLETED' ? 'Complete' : 'Will run first', status: skipWarmup ? 'warn' : 'ok' },
          { label: 'Campaign', value: campaign?.name || 'None selected', status: campaign ? 'ok' : 'warn' },
        ].map(({ label, value, status }) => (
          <div key={label} className="flex items-center justify-between text-sm">
            <span className="text-slate-400">{label}</span>
            <div className="flex items-center gap-2">
              <span className="text-slate-200">{value}</span>
              <div className={`w-1.5 h-1.5 rounded-full ${status === 'ok' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
            </div>
          </div>
        ))}
      </div>

      {/* Autonomy mode */}
      <div className="space-y-3">
        <p className="text-sm font-medium text-slate-300">Autonomy mode</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <button
            onClick={() => setMode('full')}
            className={`text-left p-4 rounded-xl border-2 transition-all ${mode === 'full' ? 'border-emerald-500 bg-emerald-500/10' : 'border-slate-700 bg-slate-900 hover:border-slate-600'}`}
          >
            <p className="font-semibold text-slate-100 text-sm mb-1">Managed (Recommended)</p>
            <p className="text-xs text-slate-400">Agent generates messages, you approve in the queue before they're sent.</p>
          </button>
          <button
            onClick={() => setMode('direct')}
            className={`text-left p-4 rounded-xl border-2 transition-all ${mode === 'direct' ? 'border-amber-500 bg-amber-500/10' : 'border-slate-700 bg-slate-900 hover:border-slate-600'}`}
          >
            <p className="font-semibold text-slate-100 text-sm mb-1">Full Autonomy</p>
            <p className="text-xs text-slate-400">Messages are sent immediately without your review. Faster but less control.</p>
          </button>
        </div>
      </div>

      {mode === 'direct' && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 text-sm text-amber-400">
          Full autonomy enables auto-approve on your campaign. Messages will be sent without human review.
        </div>
      )}

      <button
        onClick={handleLaunch}
        disabled={launching}
        className="w-full py-3.5 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 rounded-xl text-sm font-bold tracking-wide transition-colors"
      >
        {launching ? 'Launching...' : '🚀 Launch GhostAgent'}
      </button>
    </div>
  )
}

// ─── Main Onboarding Page ─────────────────────────────────────────────────────

export default function OnboardingPage() {
  const [step, setStep] = useState(0)
  const [account, setAccount] = useState<Account | null>(null)
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [skipWarmup, setSkipWarmup] = useState(false)
  const [launchingWarmup, setLaunchingWarmup] = useState(false)

  return (
    <div className="min-h-screen p-6 flex flex-col items-center justify-start pt-10">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
            Set up GhostAgent
          </h1>
          <p className="text-slate-400 text-sm mt-2">Follow the steps below to start your automated LinkedIn outreach</p>
        </div>

        <StepIndicator current={step} steps={STEPS} />

        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 sm:p-8">
          {step === 0 && (
            <StepAccount
              onDone={(acc) => {
                setAccount(acc)
                setStep(1)
              }}
            />
          )}

          {step === 1 && account && (
            <StepWarmup
              account={account}
              launching={launchingWarmup}
              onDone={(skip) => {
                setSkipWarmup(skip)
                if (!skip) {
                  setLaunchingWarmup(true)
                  api.startAgent(account.id, { continuous: true, skipWarmup: false })
                    .then(() => { window.location.href = '/live' })
                    .catch((e: any) => {
                      alert('Failed to start warmup: ' + e.message)
                      setLaunchingWarmup(false)
                    })
                } else {
                  setStep(2)
                }
              }}
            />
          )}

          {step === 2 && account && (
            <StepCampaign
              account={account}
              onDone={(c) => {
                setCampaign(c)
                setStep(3)
              }}
            />
          )}

          {step === 3 && campaign && (
            <StepProspects
              campaign={campaign}
              onDone={() => setStep(4)}
            />
          )}

          {step === 4 && account && (
            <StepLaunch
              account={account}
              campaign={campaign}
              skipWarmup={skipWarmup}
              onDone={() => {
                window.location.href = '/'
              }}
            />
          )}
        </div>

        {/* Skip to dashboard */}
        {step < 4 && (
          <p className="text-center mt-6 text-xs text-slate-600">
            Already set up?{' '}
            <a href="/" className="text-slate-400 hover:text-slate-300 underline">
              Go to dashboard
            </a>
          </p>
        )}
      </div>
    </div>
  )
}
