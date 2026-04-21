'use client'

import { useState, useEffect } from 'react'
import { api, getAccountId } from '../../lib/api'

interface AgentTask {
  id: string
  title: string
  instruction: string
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
  result?: string
  errorMessage?: string
  steps?: { step: number; action: string; reason: string; error?: string }[]
  startedAt?: string
  completedAt?: string
  createdAt: string
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    PENDING: 'bg-slate-700/50 text-slate-400 border-slate-700',
    RUNNING: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    COMPLETED: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
    FAILED: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
    CANCELLED: 'bg-slate-700/50 text-slate-500 border-slate-700',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${map[status] || map.PENDING}`}>
      {status === 'RUNNING' ? (
        <span className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse inline-block" />
          {status}
        </span>
      ) : status}
    </span>
  )
}

function TaskCard({ task, onRun, onDelete }: {
  task: AgentTask
  onRun: (id: string) => void
  onDelete: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [running, setRunning] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const handleRun = async () => {
    setRunning(true)
    await onRun(task.id)
    setRunning(false)
  }

  const handleDelete = async () => {
    if (!confirm(`Delete task "${task.title}"?`)) return
    setDeleting(true)
    await onDelete(task.id)
    setDeleting(false)
  }

  const canRun = task.status === 'PENDING' || task.status === 'FAILED' || task.status === 'COMPLETED'

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-slate-100 truncate">{task.title}</h3>
            <StatusBadge status={task.status} />
          </div>
          <p className="text-xs text-slate-400 line-clamp-2">{task.instruction}</p>
        </div>
        <div className="flex gap-2 shrink-0">
          {canRun && (
            <button
              onClick={handleRun}
              disabled={running}
              className="px-3 py-1.5 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 rounded-lg transition-colors disabled:opacity-50 font-medium"
            >
              {running ? 'Starting...' : 'Run'}
            </button>
          )}
          <button
            onClick={() => setExpanded(!expanded)}
            className="px-3 py-1.5 text-xs text-slate-400 bg-slate-800 border border-slate-700 hover:bg-slate-700 rounded-lg transition-colors"
          >
            {expanded ? 'Hide' : 'Details'}
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

      {/* Result */}
      {(task.result || task.errorMessage) && (
        <div className={`mt-3 p-3 rounded-lg text-xs ${
          task.status === 'COMPLETED'
            ? 'bg-indigo-500/10 border border-indigo-500/20 text-indigo-300'
            : 'bg-rose-500/10 border border-rose-500/20 text-rose-300'
        }`}>
          <span className="font-medium">{task.status === 'COMPLETED' ? 'Result: ' : 'Error: '}</span>
          {task.result || task.errorMessage}
        </div>
      )}

      {/* Expanded steps */}
      {expanded && (
        <div className="mt-4 space-y-2">
          <div className="text-xs text-slate-500 font-medium uppercase tracking-wider">Execution Steps</div>
          {task.steps && task.steps.length > 0 ? (
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {task.steps.map((s) => (
                <div key={s.step} className="flex items-start gap-2 text-xs py-1 border-b border-slate-800 last:border-0">
                  <span className="w-5 h-5 rounded bg-slate-800 text-slate-400 flex items-center justify-center shrink-0 font-mono">
                    {s.step}
                  </span>
                  <span className={`shrink-0 px-1.5 py-0.5 rounded text-xs font-medium ${
                    s.action === 'done' ? 'bg-indigo-500/20 text-indigo-400' :
                    s.action === 'failed' ? 'bg-rose-500/20 text-rose-400' :
                    'bg-slate-700 text-slate-300'
                  }`}>{s.action}</span>
                  <span className="text-slate-400">{s.reason}</span>
                  {s.error && <span className="text-rose-400 ml-auto shrink-0">{s.error}</span>}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-slate-600 italic">No steps recorded yet</div>
          )}
          <div className="text-xs text-slate-600 mt-2">
            Created {new Date(task.createdAt).toLocaleString()}
            {task.startedAt && ` · Started ${new Date(task.startedAt).toLocaleString()}`}
            {task.completedAt && ` · Finished ${new Date(task.completedAt).toLocaleString()}`}
          </div>
        </div>
      )}
    </div>
  )
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<AgentTask[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ title: '', instruction: '' })

  const accountId = getAccountId()

  const loadTasks = () =>
    api.getTasks().then(setTasks).catch(console.error).finally(() => setLoading(false))

  useEffect(() => {
    loadTasks()
    // Poll for status updates when a task is running
    const interval = setInterval(() => {
      loadTasks()
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!accountId || !form.title || !form.instruction) return
    setCreating(true)
    try {
      const task = await api.createTask({
        linkedInAccountId: accountId,
        title: form.title,
        instruction: form.instruction,
      })
      setTasks(prev => [task, ...prev])
      setShowCreate(false)
      setForm({ title: '', instruction: '' })
    } catch (e: any) {
      alert(e.message)
    } finally {
      setCreating(false)
    }
  }

  const handleRun = async (id: string) => {
    try {
      await api.runTask(id)
      await loadTasks()
    } catch (e: any) {
      alert('Failed to start task: ' + e.message)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await api.deleteTask(id)
      setTasks(prev => prev.filter(t => t.id !== id))
    } catch (e: any) {
      alert('Delete failed: ' + e.message)
    }
  }

  return (
    <div className="p-8 max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Tasks</h1>
          <p className="text-slate-400 text-sm mt-1">One-off instructions for the agent to execute on LinkedIn</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 rounded-lg text-sm font-medium transition-colors"
        >
          + New Task
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <form onSubmit={handleCreate} className="bg-slate-900 border border-emerald-500/30 rounded-xl p-5 space-y-4">
          <h3 className="font-semibold text-slate-100">New Task</h3>
          <div>
            <label className="text-xs text-slate-400 block mb-1">Task Title</label>
            <input
              required
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
              placeholder="e.g. Connect with CTOs at fintech startups"
              value={form.title}
              onChange={e => setForm({ ...form, title: e.target.value })}
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1">Instructions</label>
            <textarea
              required
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 resize-none"
              rows={4}
              placeholder="Describe exactly what the agent should do. E.g. Search for 'CTO fintech' on LinkedIn, visit the top 5 profiles, and send each a connection request with a note mentioning our AI product."
              value={form.instruction}
              onChange={e => setForm({ ...form, instruction: e.target.value })}
            />
          </div>
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 text-xs text-amber-400">
            The agent will open a browser and follow your instructions step by step. Be specific about what actions to take.
          </div>
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={() => setShowCreate(false)}
              className="px-4 py-2 text-sm text-slate-400 border border-slate-700 rounded-lg hover:border-slate-500 transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={creating}
              className="px-4 py-2 text-sm bg-emerald-500 hover:bg-emerald-400 rounded-lg font-medium disabled:opacity-50 transition-colors">
              {creating ? 'Creating...' : 'Create Task'}
            </button>
          </div>
        </form>
      )}

      {/* Task list */}
      {loading ? (
        <div className="text-center py-16 text-slate-500">Loading tasks...</div>
      ) : tasks.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-3">⚡</div>
          <p className="text-slate-400 font-medium">No tasks yet</p>
          <p className="text-slate-600 text-sm mt-1">Create a task to give the agent a specific one-off instruction</p>
        </div>
      ) : (
        <div className="space-y-4">
          {tasks.map(t => (
            <TaskCard key={t.id} task={t} onRun={handleRun} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  )
}
