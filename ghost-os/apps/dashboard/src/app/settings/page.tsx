'use client'

import { useState, useEffect } from 'react'
import { api, getAccountId, setAccountId, getToken, clearToken } from '../../lib/api'

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    CONNECTED: 'bg-emerald-400',
    DISCONNECTED: 'bg-slate-500',
    EXPIRED: 'bg-rose-400',
    SUSPENDED: 'bg-amber-400',
  }
  const labels: Record<string, string> = {
    CONNECTED: 'Connected',
    DISCONNECTED: 'Not connected',
    EXPIRED: 'Session expired',
    SUSPENDED: 'Suspended',
  }
  return (
    <div className="flex items-center gap-2">
      <span className={`w-2 h-2 rounded-full ${colors[status] || colors.DISCONNECTED} ${status === 'CONNECTED' ? 'animate-pulse' : ''}`} />
      <span className="text-sm text-slate-300">{labels[status] || 'Unknown'}</span>
    </div>
  )
}

export default function SettingsPage() {
  const [accounts, setAccounts] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState<string | null>(null)
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null)

  useEffect(() => {
    setSelectedAccountId(getAccountId())
    api.getAccounts()
      .then(setAccounts)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const handleCreateAccount = async () => {
    try {
      const account = await api.createAccount()
      setAccounts(prev => [account, ...prev])
    } catch (e: any) {
      alert(e.message)
    }
  }

  const handleConnect = async (accountId: string) => {
    setConnecting(accountId)
    try {
      await api.connectLinkedIn(accountId)
      alert('Login browser started! Check the Live View page to complete login.')
    } catch (e: any) {
      alert('Error: ' + e.message)
    } finally {
      setConnecting(null)
    }
  }

  const handleSelectAccount = (accountId: string) => {
    setAccountId(accountId)
    setSelectedAccountId(accountId)
  }

  const handleLogout = () => {
    clearToken()
    window.location.href = '/login'
  }

  const warmupLabel: Record<string, string> = {
    NOT_STARTED: 'Not started',
    DAY_1: 'Day 1 in progress',
    DAY_2: 'Day 2 in progress',
    COMPLETED: 'Complete',
  }

  return (
    <div className="p-8 max-w-2xl space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Settings</h1>
          <p className="text-slate-400 text-sm mt-1">Manage LinkedIn accounts and preferences</p>
        </div>
        <button onClick={handleLogout}
          className="px-3 py-1.5 text-xs text-slate-400 border border-slate-700 hover:border-slate-500 rounded-lg transition-colors">
          Log out
        </button>
      </div>

      {/* LinkedIn Accounts */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-slate-200">LinkedIn Accounts</h2>
          <button onClick={handleCreateAccount}
            className="px-3 py-1.5 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 rounded-lg transition-colors">
            + Add Account
          </button>
        </div>

        {loading ? (
          <p className="text-slate-500 text-sm">Loading...</p>
        ) : accounts.length === 0 ? (
          <div className="text-center py-6">
            <p className="text-slate-400 text-sm">No accounts yet</p>
            <button onClick={handleCreateAccount}
              className="mt-3 px-4 py-2 bg-emerald-500 hover:bg-emerald-400 rounded-lg text-sm font-medium transition-colors">
              Connect LinkedIn
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {accounts.map(account => (
              <div key={account.id}
                className={`border rounded-xl p-4 transition-colors ${
                  selectedAccountId === account.id
                    ? 'border-emerald-500/40 bg-emerald-500/5'
                    : 'border-slate-700 hover:border-slate-600'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-slate-200 text-sm">
                      {account.linkedInName || 'Unnamed Account'}
                    </p>
                    {account.linkedInHeadline && (
                      <p className="text-xs text-slate-500 mt-0.5">{account.linkedInHeadline}</p>
                    )}
                    <div className="mt-2">
                      <StatusDot status={account.sessionStatus} />
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    {selectedAccountId !== account.id && (
                      <button onClick={() => handleSelectAccount(account.id)}
                        className="px-3 py-1 text-xs text-slate-400 border border-slate-700 hover:border-slate-500 rounded-lg transition-colors">
                        Use this account
                      </button>
                    )}
                    {selectedAccountId === account.id && (
                      <span className="text-xs text-emerald-400 font-medium">Active</span>
                    )}
                    <button
                      onClick={() => handleConnect(account.id)}
                      disabled={connecting === account.id}
                      className="px-3 py-1 text-xs text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 hover:bg-indigo-500/20 rounded-lg transition-colors disabled:opacity-50"
                    >
                      {connecting === account.id ? 'Starting...' : account.sessionStatus === 'CONNECTED' ? 'Re-login' : 'Login with LinkedIn'}
                    </button>
                  </div>
                </div>

                {/* Warmup status */}
                <div className="mt-3 pt-3 border-t border-slate-800 flex items-center justify-between text-xs">
                  <span className="text-slate-500">Warmup: {warmupLabel[account.warmupStatus] || account.warmupStatus}</span>
                  <span className={`font-medium ${
                    account.agentStatus === 'RUNNING' ? 'text-emerald-400' :
                    account.agentStatus === 'ERROR' ? 'text-rose-400' : 'text-slate-500'
                  }`}>
                    Agent: {account.agentStatus}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="pt-2 border-t border-slate-800">
          <p className="text-xs text-slate-600">
            Click "Login with LinkedIn" to open a browser window in Live View. Log into LinkedIn there — your session is saved automatically.
          </p>
        </div>
      </div>

      {/* How it works */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
        <h2 className="font-semibold text-slate-200">How onboarding works</h2>
        <div className="space-y-3">
          {[
            { step: '1', text: 'Add a LinkedIn account above', done: accounts.length > 0 },
            { step: '2', text: 'Click "Login with LinkedIn" → complete login in Live View', done: accounts.some(a => a.sessionStatus === 'CONNECTED') },
            { step: '3', text: '48-hour warmup runs automatically in the background', done: accounts.some(a => a.warmupStatus === 'COMPLETED') },
            { step: '4', text: 'Create a campaign, upload your prospect CSV', done: false },
            { step: '5', text: 'Agent generates messages → review and approve in Queue', done: false },
            { step: '6', text: 'Approved messages sent automatically in the next session', done: false },
          ].map(({ step, text, done }) => (
            <div key={step} className="flex items-start gap-3">
              <div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 ${
                done ? 'bg-emerald-500 text-white' : 'bg-slate-800 text-slate-500'
              }`}>
                {done ? '✓' : step}
              </div>
              <span className={`text-sm ${done ? 'text-slate-400 line-through' : 'text-slate-300'}`}>{text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
