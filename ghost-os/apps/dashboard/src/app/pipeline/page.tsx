'use client'

import { useState, useEffect } from 'react'
import { api, getAccountId } from '../../lib/api'

const STAGES = [
  { key: 'PENDING', label: 'Pending', color: 'border-slate-700 bg-slate-800/30', badge: 'bg-slate-700 text-slate-300' },
  { key: 'REQUESTED', label: 'Requested', color: 'border-cyan-500/30 bg-cyan-500/5', badge: 'bg-cyan-500/20 text-cyan-400' },
  { key: 'CONNECTED', label: 'Connected', color: 'border-emerald-500/30 bg-emerald-500/5', badge: 'bg-emerald-500/20 text-emerald-400' },
  { key: 'MESSAGED', label: 'Messaged', color: 'border-indigo-500/30 bg-indigo-500/5', badge: 'bg-indigo-500/20 text-indigo-400' },
  { key: 'REPLIED', label: 'Replied', color: 'border-violet-500/30 bg-violet-500/5', badge: 'bg-violet-500/20 text-violet-400' },
  { key: 'LEAD', label: 'Lead 🎯', color: 'border-amber-500/30 bg-amber-500/5', badge: 'bg-amber-500/20 text-amber-400' },
]

interface Prospect {
  id: string
  name: string | null
  headline: string | null
  company: string | null
  linkedInUrl: string
  status: string
  requestedAt: string | null
  connectedAt: string | null
  messagedAt: string | null
  repliedAt: string | null
  campaignName: string
}

function ProspectCard({ p }: { p: Prospect }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 hover:border-slate-700 transition-colors">
      <div className="flex items-start gap-2.5">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-600 to-cyan-600 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
          {(p.name || '?')[0].toUpperCase()}
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-200 truncate">{p.name || 'Unknown'}</p>
          {p.headline && <p className="text-xs text-slate-500 truncate">{p.headline}</p>}
          {p.company && <p className="text-xs text-slate-600 truncate">{p.company}</p>}
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-slate-600">{p.campaignName}</span>
        <a
          href={p.linkedInUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
        >
          View →
        </a>
      </div>
    </div>
  )
}

export default function PipelinePage() {
  const [prospects, setProspects] = useState<Prospect[]>([])
  const [stats, setStats] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')

  const accountId = getAccountId()

  useEffect(() => {
    if (!accountId) { setLoading(false); return }
    api.getPipeline(accountId)
      .then(data => {
        setProspects(data.prospects || [])
        setStats(data.stats || {})
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [accountId])

  const filtered = prospects.filter(p =>
    !filter ||
    (p.name?.toLowerCase().includes(filter.toLowerCase())) ||
    (p.company?.toLowerCase().includes(filter.toLowerCase()))
  )

  const total = prospects.length
  const leads = stats['LEAD'] || 0
  const replies = stats['REPLIED'] || 0

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Pipeline</h1>
          <p className="text-slate-400 text-sm mt-1">
            {total} total prospects · {leads} leads · {replies > 0 ? `${Math.round((leads / total) * 100)}% conversion` : '—'}
          </p>
        </div>
        <input
          className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-slate-500 w-56"
          placeholder="Filter by name or company..."
          value={filter}
          onChange={e => setFilter(e.target.value)}
        />
      </div>

      {loading ? (
        <div className="text-center py-16 text-slate-500">Loading pipeline...</div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 overflow-x-auto">
          {STAGES.map(stage => {
            const stageProspects = filtered.filter(p => p.status === stage.key)
            return (
              <div key={stage.key} className={`rounded-xl border ${stage.color} flex flex-col min-h-[400px]`}>
                <div className="p-3 border-b border-slate-800/50 flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-300">{stage.label}</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${stage.badge}`}>
                    {stats[stage.key] || 0}
                  </span>
                </div>
                <div className="flex-1 p-2 space-y-2 overflow-y-auto">
                  {stageProspects.slice(0, 20).map(p => (
                    <ProspectCard key={p.id} p={p} />
                  ))}
                  {stageProspects.length === 0 && (
                    <p className="text-xs text-slate-700 text-center py-4">Empty</p>
                  )}
                  {stageProspects.length > 20 && (
                    <p className="text-xs text-slate-600 text-center py-2">
                      +{stageProspects.length - 20} more
                    </p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
