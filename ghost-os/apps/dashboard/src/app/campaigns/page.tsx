'use client'

import { useState, useEffect, useRef } from 'react'
import { api, getAccountId } from '../../lib/api'

interface Campaign {
  id: string
  name: string
  goal: string
  status: string
  linkedInAccountId: string
  dailyConnectionLimit: number
  autoApprove: boolean
  createdAt: string
  prospectCount: number
  pendingCount: number
  requestedCount: number
  repliedCount: number
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    ACTIVE: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    DRAFT: 'bg-slate-700/50 text-slate-400 border-slate-700',
    PAUSED: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    COMPLETED: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${map[status] || map.DRAFT}`}>
      {status}
    </span>
  )
}

function CampaignCard({ campaign, onStatusChange, onUpload, onDelete, onLaunch }: {
  campaign: Campaign
  onStatusChange: (id: string, status: string) => void
  onUpload: (id: string, file: File) => void
  onDelete: (id: string) => void
  onLaunch: (accountId: string) => void
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [launching, setLaunching] = useState(false)

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    await onUpload(campaign.id, file)
    setUploading(false)
    e.target.value = ''
  }

  const toggle = () => {
    const next = campaign.status === 'ACTIVE' ? 'PAUSED' : 'ACTIVE'
    onStatusChange(campaign.id, next)
  }

  const handleDelete = async () => {
    if (!confirm(`Delete campaign "${campaign.name}"? This will remove all prospects and messages.`)) return
    setDeleting(true)
    await onDelete(campaign.id)
    setDeleting(false)
  }

  const handleLaunch = async () => {
    setLaunching(true)
    await onLaunch(campaign.linkedInAccountId)
    setLaunching(false)
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-slate-100">{campaign.name}</h3>
            <StatusBadge status={campaign.status} />
          </div>
          <p className="text-xs text-slate-400 max-w-md">{campaign.goal}</p>
        </div>
        <div className="flex gap-2">
          {campaign.status === 'ACTIVE' && (
            <button
              onClick={handleLaunch}
              disabled={launching}
              className="px-3 py-1.5 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 rounded-lg transition-colors disabled:opacity-50 font-medium"
            >
              {launching ? 'Launching...' : 'Run Now'}
            </button>
          )}
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="px-3 py-1.5 text-xs text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 hover:bg-indigo-500/20 rounded-lg transition-colors disabled:opacity-50"
          >
            {uploading ? 'Uploading...' : 'Import CSV'}
          </button>
          <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleFile} />
          <button
            onClick={toggle}
            className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
              campaign.status === 'ACTIVE'
                ? 'text-amber-400 bg-amber-500/10 border-amber-500/20 hover:bg-amber-500/20'
                : 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20 hover:bg-emerald-500/20'
            }`}
          >
            {campaign.status === 'ACTIVE' ? 'Pause' : 'Activate'}
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="px-3 py-1.5 text-xs text-red-400 bg-red-500/10 border border-red-500/20 hover:bg-red-500/20 rounded-lg transition-colors disabled:opacity-50"
          >
            {deleting ? '...' : 'Delete'}
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3 mt-4">
        {[
          { label: 'Total', value: campaign.prospectCount, color: 'text-slate-300' },
          { label: 'Pending', value: campaign.pendingCount, color: 'text-slate-400' },
          { label: 'Requested', value: campaign.requestedCount, color: 'text-cyan-400' },
          { label: 'Replied', value: campaign.repliedCount, color: 'text-emerald-400' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-slate-950/50 rounded-lg p-3 text-center">
            <p className={`text-xl font-bold ${color}`}>{value || 0}</p>
            <p className="text-xs text-slate-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-4 text-xs text-slate-500">
        <span>Daily limit: {campaign.dailyConnectionLimit} connects</span>
        {campaign.autoApprove && <span className="text-amber-400">Auto-send enabled</span>}
        <span className="ml-auto">{new Date(campaign.createdAt).toLocaleDateString()}</span>
      </div>
    </div>
  )
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({
    name: '', goal: '', personaTone: 'professional',
    dailyConnectionLimit: 15, autoApprove: false
  })

  const accountId = getAccountId()

  const handleLaunch = async (linkedInAccountId: string) => {
    try {
      await api.startAgent(linkedInAccountId, { continuous: false, skipWarmup: true })
      alert('Agent launched! Check the Live View for progress.')
    } catch (e: any) {
      alert('Launch failed: ' + e.message)
    }
  }

  useEffect(() => {
    api.getCampaigns().then(data => setCampaigns(data)).catch(console.error).finally(() => setLoading(false))
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!accountId || !form.name || !form.goal) return
    setCreating(true)
    try {
      const campaign = await api.createCampaign({ ...form, linkedInAccountId: accountId })
      setCampaigns(prev => [campaign, ...prev])
      setShowCreate(false)
      setForm({ name: '', goal: '', personaTone: 'professional', dailyConnectionLimit: 15, autoApprove: false })
    } catch (e: any) {
      alert(e.message)
    } finally {
      setCreating(false)
    }
  }

  const handleStatusChange = async (id: string, status: string) => {
    await api.updateCampaignStatus(id, status)
    setCampaigns(prev => prev.map(c => c.id === id ? { ...c, status } : c))
  }

  const handleUpload = async (campaignId: string, file: File) => {
    try {
      const result = await api.uploadProspects(campaignId, file)
      alert(`Imported ${result.imported} prospects`)
      const data = await api.getCampaigns()
      setCampaigns(data)
    } catch (e: any) {
      alert('Upload failed: ' + e.message)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await api.deleteCampaign(id)
      setCampaigns(prev => prev.filter(c => c.id !== id))
    } catch (e: any) {
      alert('Delete failed: ' + e.message)
    }
  }

  return (
    <div className="p-8 max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Campaigns</h1>
          <p className="text-slate-400 text-sm mt-1">Manage your LinkedIn outreach campaigns</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 rounded-lg text-sm font-medium transition-colors"
        >
          + New Campaign
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <form onSubmit={handleCreate} className="bg-slate-900 border border-emerald-500/30 rounded-xl p-5 space-y-4">
          <h3 className="font-semibold text-slate-100">New Campaign</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-slate-400 block mb-1">Campaign Name</label>
              <input
                required
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
                placeholder="Q2 Outreach"
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Daily Connection Limit</label>
              <input
                type="number" min={1} max={25}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
                value={form.dailyConnectionLimit}
                onChange={e => setForm({ ...form, dailyConnectionLimit: parseInt(e.target.value) })}
              />
            </div>
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1">Campaign Goal</label>
            <textarea
              required
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 resize-none"
              rows={2}
              placeholder="Book a demo call for our B2B SaaS product with VPs of Sales"
              value={form.goal}
              onChange={e => setForm({ ...form, goal: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-slate-400 block mb-1">Message Tone</label>
              <select
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
                value={form.personaTone}
                onChange={e => setForm({ ...form, personaTone: e.target.value })}
              >
                <option value="professional">Professional</option>
                <option value="casual">Casual & Friendly</option>
                <option value="punchy">Short & Punchy</option>
              </select>
            </div>
            <div className="flex items-end pb-0.5">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  className="rounded"
                  checked={form.autoApprove}
                  onChange={e => setForm({ ...form, autoApprove: e.target.checked })}
                />
                <span className="text-sm text-slate-400">Auto-send without review</span>
              </label>
            </div>
          </div>
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={() => setShowCreate(false)}
              className="px-4 py-2 text-sm text-slate-400 border border-slate-700 rounded-lg hover:border-slate-500 transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={creating}
              className="px-4 py-2 text-sm bg-emerald-500 hover:bg-emerald-400 rounded-lg font-medium disabled:opacity-50 transition-colors">
              {creating ? 'Creating...' : 'Create Campaign'}
            </button>
          </div>
        </form>
      )}

      {/* Campaign list */}
      {loading ? (
        <div className="text-center py-16 text-slate-500">Loading campaigns...</div>
      ) : campaigns.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-3">📣</div>
          <p className="text-slate-400 font-medium">No campaigns yet</p>
          <p className="text-slate-600 text-sm mt-1">Create your first campaign to start outreach</p>
        </div>
      ) : (
        <div className="space-y-4">
          {campaigns.map(c => (
            <CampaignCard key={c.id} campaign={c} onStatusChange={handleStatusChange} onUpload={handleUpload} onDelete={handleDelete} onLaunch={handleLaunch} />
          ))}
        </div>
      )}

      {/* CSV format hint */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
        <p className="text-xs text-slate-500 font-medium mb-1">CSV Import Format</p>
        <p className="text-xs text-slate-600 font-mono">linkedInUrl, name, headline, company, notes</p>
        <p className="text-xs text-slate-600 mt-1">Column names are flexible — we detect common variations automatically.</p>
      </div>
    </div>
  )
}
