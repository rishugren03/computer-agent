'use client'

import { useState, useEffect } from 'react'
import { api, getAccountId } from '../lib/api'

function StatCard({ label, value, limit, color }: {
  label: string; value: number; limit?: number; color: string
}) {
  const pct = limit ? Math.min((value / limit) * 100, 100) : null
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">{label}</p>
      <div className="flex items-end gap-2">
        <span className={`text-3xl font-bold ${color}`}>{value}</span>
        {limit && <span className="text-slate-500 text-sm mb-1">/ {limit}</span>}
      </div>
      {pct !== null && (
        <div className="mt-3 h-1.5 bg-slate-800 rounded-full">
          <div
            className={`h-full rounded-full ${color.replace('text-', 'bg-')} transition-all`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    RUNNING: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    IDLE: 'bg-slate-700/50 text-slate-400 border-slate-700',
    WARMUP: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    ERROR: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
    PAUSED: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    COMPLETED: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
    ABORTED: 'bg-slate-700/50 text-slate-400 border-slate-700',
  }
  const dot: Record<string, string> = {
    RUNNING: 'bg-emerald-400', IDLE: 'bg-slate-500', WARMUP: 'bg-amber-400',
    ERROR: 'bg-rose-400', PAUSED: 'bg-blue-400', COMPLETED: 'bg-indigo-400', ABORTED: 'bg-slate-500',
  }
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${colors[status] || colors.IDLE}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot[status] || 'bg-slate-500'} ${status === 'RUNNING' ? 'animate-pulse' : ''}`} />
      {status}
    </span>
  )
}

function StartAgentModal({ onClose, onStart }: {
  onClose: () => void
  onStart: (opts: { skipWarmup: boolean }) => void
}) {
  const [skipWarmup, setSkipWarmup] = useState(false)
  const [starting, setStarting] = useState(false)

  const handleStart = async () => {
    setStarting(true)
    await onStart({ skipWarmup })
    setStarting(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 w-full max-w-sm shadow-2xl">
        <h3 className="text-lg font-bold text-slate-100 mb-1">Start Agent</h3>
        <p className="text-slate-400 text-sm mb-5">Configure how the agent should run.</p>

        <div className="space-y-3 mb-6">
          <label className="flex items-start gap-3 cursor-pointer group">
            <div
              onClick={() => setSkipWarmup(!skipWarmup)}
              className={`mt-0.5 w-10 h-5 rounded-full transition-colors relative shrink-0 ${skipWarmup ? 'bg-amber-500' : 'bg-slate-700 group-hover:bg-slate-600'}`}
            >
              <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${skipWarmup ? 'translate-x-5' : 'translate-x-0.5'}`} />
            </div>
            <div>
              <p className="text-sm text-slate-200 font-medium">Skip warmup</p>
              <p className="text-xs text-slate-500 mt-0.5">Start outreach immediately. Higher detection risk on new accounts.</p>
            </div>
          </label>
        </div>

        {skipWarmup && (
          <div className="mb-5 bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 text-xs text-amber-400">
            Warmup builds account trust over 48h before outreach. Skipping increases ban risk on fresh accounts.
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 text-sm text-slate-400 border border-slate-700 hover:border-slate-500 rounded-xl transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleStart}
            disabled={starting}
            className="flex-1 py-2.5 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 rounded-xl text-sm font-semibold transition-colors"
          >
            {starting ? 'Starting...' : 'Launch Agent'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function OverviewPage() {
  const [stats, setStats] = useState<any>(null)
  const [agentStatus, setAgentStatus] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [showStartModal, setShowStartModal] = useState(false)
  const [stopping, setStopping] = useState(false)

  const accountId = getAccountId()

  useEffect(() => {
    if (!accountId) { setLoading(false); return }
    Promise.all([
      api.getAccountStats(accountId),
      api.getAgentStatus(accountId),
    ]).then(([s, a]) => {
      setStats(s)
      setAgentStatus(a)
    }).catch(console.error).finally(() => setLoading(false))
  }, [accountId])

  const handleStart = async ({ skipWarmup }: { skipWarmup: boolean }) => {
    if (!accountId) return
    try {
      await api.startAgent(accountId, { continuous: true, skipWarmup })
      const a = await api.getAgentStatus(accountId)
      setAgentStatus(a)
      setShowStartModal(false)
    } catch (e: any) {
      alert(e.message)
      setShowStartModal(false)
    }
  }

  const handleStop = async () => {
    if (!accountId) return
    setStopping(true)
    try {
      await api.stopAgent(accountId)
      setTimeout(async () => {
        const a = await api.getAgentStatus(accountId)
        setAgentStatus(a)
        setStopping(false)
      }, 2000)
    } catch {
      setStopping(false)
    }
  }

  if (!accountId) {
    return (
      <div className="p-8 flex items-center justify-center min-h-screen">
        <div className="text-center space-y-5 max-w-sm">
          <div className="w-16 h-16 rounded-full bg-slate-800 flex items-center justify-center mx-auto">
            <span className="text-3xl">👻</span>
          </div>
          <h2 className="text-xl font-semibold text-slate-100">Welcome to GhostAgent</h2>
          <p className="text-slate-400 text-sm">Your AI-powered LinkedIn outreach platform. Let's get you set up.</p>
          <a
            href="/onboarding"
            className="inline-block px-6 py-3 bg-emerald-500 hover:bg-emerald-400 rounded-xl text-sm font-semibold transition-colors"
          >
            Start Setup →
          </a>
          <p className="text-slate-600 text-xs">
            Already have an account?{' '}
            <a href="/settings" className="text-slate-400 hover:text-slate-300 underline">Go to Settings</a>
          </p>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-screen">
        <div className="text-slate-500 text-sm">Loading dashboard...</div>
      </div>
    )
  }

  const today = stats?.today || {}
  const pipeline = stats?.pipeline || {}
  const queue = stats?.queue || {}
  const agentRunning = agentStatus?.agentStatus === 'RUNNING'

  return (
    <>
      {showStartModal && (
        <StartAgentModal
          onClose={() => setShowStartModal(false)}
          onStart={handleStart}
        />
      )}

      <div className="p-8 space-y-8 max-w-6xl">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-100">Overview</h1>
            <p className="text-slate-400 text-sm mt-1">
              {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {agentStatus && <StatusBadge status={agentStatus.agentStatus || 'IDLE'} />}
            {agentRunning ? (
              <button
                onClick={handleStop}
                disabled={stopping}
                className="px-4 py-2 bg-rose-500/20 text-rose-400 border border-rose-500/30 hover:bg-rose-500/30 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
              >
                {stopping ? 'Stopping...' : 'Stop Agent'}
              </button>
            ) : (
              <button
                onClick={() => setShowStartModal(true)}
                className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 rounded-lg text-sm font-medium transition-colors"
              >
                Start Agent
              </button>
            )}
          </div>
        </div>

        {/* Warmup banner */}
        {agentStatus?.warmupStatus && agentStatus.warmupStatus !== 'COMPLETED' && (
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="text-amber-400 text-lg">🔥</span>
              <div>
                <p className="text-amber-400 font-medium text-sm">
                  Warmup in progress: {agentStatus.warmupStatus}
                </p>
                <p className="text-slate-400 text-xs">Agent is building LinkedIn trust. Outreach unlocks after 48h warmup.</p>
              </div>
            </div>
            <a
              href="/onboarding"
              className="shrink-0 text-xs text-amber-400 border border-amber-500/30 px-3 py-1.5 rounded-lg hover:bg-amber-500/10 transition-colors"
            >
              Onboarding →
            </a>
          </div>
        )}

        {/* No campaigns prompt */}
        {!loading && Object.keys(pipeline).length === 0 && (
          <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-xl p-5 flex items-center justify-between gap-3">
            <div>
              <p className="text-indigo-300 font-medium text-sm">No prospects yet</p>
              <p className="text-slate-500 text-xs mt-0.5">Create a campaign and upload your prospect list to start outreach.</p>
            </div>
            <div className="flex gap-2 shrink-0">
              <a href="/campaigns" className="text-xs text-indigo-400 border border-indigo-500/30 px-3 py-1.5 rounded-lg hover:bg-indigo-500/10 transition-colors">
                Create Campaign
              </a>
            </div>
          </div>
        )}

        {/* Today's activity */}
        <div>
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Today's Activity</h2>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            <StatCard label="Connections Sent" value={today.connections || 0} limit={25} color="text-emerald-400" />
            <StatCard label="Profile Views" value={today.profileViews || 0} limit={80} color="text-cyan-400" />
            <StatCard label="Likes" value={today.likes || 0} limit={30} color="text-indigo-400" />
            <StatCard label="Comments" value={today.comments || 0} limit={15} color="text-violet-400" />
            <StatCard label="Messages Gen." value={today.messages || 0} limit={50} color="text-rose-400" />
          </div>
        </div>

        {/* Pipeline & Queue */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-300">Pipeline</h3>
              <a href="/pipeline" className="text-xs text-slate-500 hover:text-slate-300 transition-colors">View all →</a>
            </div>
            <div className="space-y-3">
              {[
                { label: 'Pending', key: 'PENDING', color: 'text-slate-400 bg-slate-700' },
                { label: 'Requested', key: 'REQUESTED', color: 'text-cyan-400 bg-cyan-500/20' },
                { label: 'Connected', key: 'CONNECTED', color: 'text-emerald-400 bg-emerald-500/20' },
                { label: 'Messaged', key: 'MESSAGED', color: 'text-indigo-400 bg-indigo-500/20' },
                { label: 'Replied', key: 'REPLIED', color: 'text-violet-400 bg-violet-500/20' },
                { label: 'Lead', key: 'LEAD', color: 'text-amber-400 bg-amber-500/20' },
              ].map(({ label, key, color }) => (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-slate-400 text-sm">{label}</span>
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${color}`}>
                    {pipeline[key] || 0}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-300">Approval Queue</h3>
              <a href="/queue" className="text-xs text-slate-500 hover:text-slate-300 transition-colors">Review →</a>
            </div>
            <div className="space-y-3">
              {[
                { label: 'Pending Review', key: 'PENDING_REVIEW', color: 'text-amber-400 bg-amber-500/20' },
                { label: 'Approved', key: 'APPROVED', color: 'text-emerald-400 bg-emerald-500/20' },
                { label: 'Rejected', key: 'REJECTED', color: 'text-rose-400 bg-rose-500/20' },
                { label: 'Sent', key: 'SENT', color: 'text-slate-400 bg-slate-700' },
              ].map(({ label, key, color }) => (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-slate-400 text-sm">{label}</span>
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${color}`}>
                    {queue[key] || 0}
                  </span>
                </div>
              ))}
            </div>
            {(queue['PENDING_REVIEW'] || 0) > 0 && (
              <a
                href="/queue"
                className="mt-4 block text-center py-2 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-lg text-sm hover:bg-emerald-500/20 transition-colors"
              >
                Review {queue['PENDING_REVIEW']} messages →
              </a>
            )}
          </div>
        </div>

        {/* Recent sessions */}
        {agentStatus?.recentSessions?.length > 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Recent Sessions</h3>
            <div className="space-y-2">
              {agentStatus.recentSessions.map((s: any) => (
                <div key={s.id} className="flex items-center justify-between py-2 border-b border-slate-800 last:border-0">
                  <div className="flex items-center gap-3">
                    <StatusBadge status={s.status} />
                    <span className="text-xs text-slate-500">{new Date(s.startedAt).toLocaleString()}</span>
                  </div>
                  <div className="flex gap-4 text-xs text-slate-500">
                    <span>{s.connectionsSent} connects</span>
                    <span>{s.likes} likes</span>
                    <span>{s.comments} comments</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  )
}
