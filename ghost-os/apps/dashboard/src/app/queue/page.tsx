'use client'

import { useState, useEffect, useCallback } from 'react'
import { api, getAccountId } from '../../lib/api'

interface Message {
  id: string
  type: string
  content: string
  status: string
  createdAt: string
  prospect: {
    id: string
    name: string
    headline: string
    company: string
    linkedInUrl: string
  }
  campaignName: string
  campaignGoal: string
}

function MessageCard({
  msg,
  onApprove,
  onReject,
}: {
  msg: Message
  onApprove: (id: string, content?: string) => void
  onReject: (id: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [editedContent, setEditedContent] = useState(msg.content)
  const [loading, setLoading] = useState(false)

  const approve = async () => {
    setLoading(true)
    await onApprove(msg.id, editing ? editedContent : undefined)
    setLoading(false)
  }

  const reject = async () => {
    setLoading(true)
    await onReject(msg.id)
    setLoading(false)
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
      {/* Prospect info */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center text-sm font-bold">
              {(msg.prospect.name || '?')[0].toUpperCase()}
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-100">{msg.prospect.name || 'Unknown'}</p>
              <p className="text-xs text-slate-400">{msg.prospect.headline}</p>
            </div>
          </div>
          {msg.prospect.company && (
            <p className="text-xs text-slate-500 mt-1 ml-10">{msg.prospect.company}</p>
          )}
        </div>
        <div className="text-right">
          <span className="text-xs text-slate-600">{msg.campaignName}</span>
          <p className="text-xs text-slate-500 mt-0.5">{new Date(msg.createdAt).toLocaleDateString()}</p>
        </div>
      </div>

      {/* Message content */}
      {editing ? (
        <textarea
          className="w-full bg-slate-950 border border-indigo-500/50 rounded-lg p-3 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none"
          rows={4}
          value={editedContent}
          onChange={(e) => setEditedContent(e.target.value)}
          maxLength={300}
        />
      ) : (
        <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-3">
          <p className="text-sm text-slate-300 leading-relaxed">{msg.content}</p>
        </div>
      )}

      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-600">{(editing ? editedContent : msg.content).length}/300 chars</span>
        <div className="flex gap-2">
          <button
            onClick={() => setEditing(!editing)}
            className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 border border-slate-700 hover:border-slate-600 rounded-lg transition-colors"
          >
            {editing ? 'Cancel' : 'Edit'}
          </button>
          <button
            onClick={reject}
            disabled={loading}
            className="px-3 py-1.5 text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 hover:bg-rose-500/20 rounded-lg transition-colors disabled:opacity-50"
          >
            Reject
          </button>
          <button
            onClick={approve}
            disabled={loading}
            className="px-3 py-1.5 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {loading ? '...' : 'Approve'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function QueuePage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [stats, setStats] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [bulkLoading, setBulkLoading] = useState(false)

  const accountId = getAccountId()

  const load = useCallback(async () => {
    if (!accountId) return
    try {
      const data = await api.getQueue(accountId)
      setMessages(data.messages || [])
      setStats(data.stats || {})
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [accountId])

  useEffect(() => { load() }, [load])

  const handleApprove = async (id: string, editedContent?: string) => {
    await api.approveMessage(id, editedContent)
    setMessages(prev => prev.filter(m => m.id !== id))
  }

  const handleReject = async (id: string) => {
    await api.rejectMessage(id)
    setMessages(prev => prev.filter(m => m.id !== id))
  }

  const handleBulk = async (action: 'approve' | 'reject') => {
    if (!accountId) return
    setBulkLoading(true)
    try {
      const result = await api.bulkQueueAction(accountId, action)
      await load()
      alert(`${action === 'approve' ? 'Approved' : 'Rejected'} ${result.updated} messages`)
    } catch (e: any) {
      alert(e.message)
    } finally {
      setBulkLoading(false)
    }
  }

  const pending = stats['PENDING_REVIEW'] || messages.length

  return (
    <div className="p-8 max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Approval Queue</h1>
          <p className="text-slate-400 text-sm mt-1">
            Review AI-generated connection notes before they're sent
          </p>
        </div>
        {messages.length > 0 && (
          <div className="flex gap-2">
            <button
              onClick={() => handleBulk('reject')}
              disabled={bulkLoading}
              className="px-4 py-2 text-sm text-rose-400 bg-rose-500/10 border border-rose-500/20 hover:bg-rose-500/20 rounded-lg transition-colors disabled:opacity-50"
            >
              Reject All
            </button>
            <button
              onClick={() => handleBulk('approve')}
              disabled={bulkLoading}
              className="px-4 py-2 text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              Approve All ({messages.length})
            </button>
          </div>
        )}
      </div>

      {/* Stats strip */}
      <div className="flex gap-4 text-xs">
        {[
          { label: 'Pending', val: stats['PENDING_REVIEW'] || 0, color: 'text-amber-400' },
          { label: 'Approved', val: stats['APPROVED'] || 0, color: 'text-emerald-400' },
          { label: 'Sent', val: stats['SENT'] || 0, color: 'text-slate-400' },
          { label: 'Rejected', val: stats['REJECTED'] || 0, color: 'text-rose-400' },
        ].map(({ label, val, color }) => (
          <div key={label} className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-2">
            <p className="text-slate-500">{label}</p>
            <p className={`text-lg font-bold ${color}`}>{val}</p>
          </div>
        ))}
      </div>

      {/* Messages */}
      {loading ? (
        <div className="text-center py-16 text-slate-500">Loading queue...</div>
      ) : messages.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-3">✅</div>
          <p className="text-slate-400 font-medium">Queue is empty</p>
          <p className="text-slate-600 text-sm mt-1">New messages will appear here after the agent visits prospect profiles</p>
        </div>
      ) : (
        <div className="space-y-4">
          {messages.map(msg => (
            <MessageCard key={msg.id} msg={msg} onApprove={handleApprove} onReject={handleReject} />
          ))}
        </div>
      )}
    </div>
  )
}
