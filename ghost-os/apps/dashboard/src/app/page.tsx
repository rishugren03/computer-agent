'use client'

import React, { useState, useEffect, useRef } from 'react'

export default function CampaignDashboard() {
  const [prospects, setProspects] = useState('')
  const [status, setStatus] = useState('Idle')
  const [taskId, setTaskId] = useState('')
  const [liveStream, setLiveStream] = useState<string | null>(null)
  
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // Connect to FastAPI WebSocket for the Live View
    const ws = new WebSocket('ws://localhost:8000/ws/live')
    
    ws.onopen = () => {
      console.log('Connected to Ghost-OS Live View Stream')
      wsRef.current = ws
    }
    
    ws.onmessage = (event) => {
      // The worker pushes base64 jpeg frames natively via Redis PubSub
      setLiveStream(`data:image/jpeg;base64,${event.data}`)
      setStatus('Running')
    }
    
    ws.onclose = () => {
      console.log('Live View Stream Disconnected')
      wsRef.current = null
    }

    return () => {
      if (wsRef.current) wsRef.current.close()
    }
  }, [])

  const startCampaign = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!prospects.trim()) return

    setStatus('Starting...')
    try {
      const res = await fetch('http://localhost:8000/start-campaign', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prospects })
      })
      const data = await res.json()
      if (data.status === 'success') {
        setTaskId(data.task_id)
        setStatus('Waking up worker node...')
      } else {
        setStatus('Error: ' + data.message)
      }
    } catch (err: any) {
      setStatus('Failed to connect to agent-api: ' + err.message)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-8 font-sans">
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Header */}
        <header className="flex items-center justify-between border-b border-slate-800 pb-6">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent drop-shadow-sm">
              Ghost-OS Console
            </h1>
            <p className="text-slate-400 mt-2 text-sm">LinkedIn Digital Twin Orchestrator</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="relative flex h-3 w-3">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${status === 'Running' ? 'bg-emerald-400' : 'bg-amber-400'}`}></span>
              <span className={`relative inline-flex rounded-full h-3 w-3 ${status === 'Running' ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
            </span>
            <span className="text-sm font-medium text-slate-300">Agent Status: {status}</span>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Campaign Builder */}
          <div className="lg:col-span-1 bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl">
            <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
              <span className="p-2 bg-indigo-500/20 text-indigo-400 rounded-md shadow-inner">🎯</span>
              Campaign Builder
            </h2>
            <form onSubmit={startCampaign} className="space-y-6">
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-400 block">Target Prospects (One per line)</label>
                <textarea 
                  className="w-full h-48 bg-slate-950 border border-slate-800 rounded-lg p-4 text-sm text-slate-200 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all outline-none resize-none shadow-inner"
                  placeholder="e.g. John Doe&#10;Jane Smith&#10;Elon Musk"
                  value={prospects}
                  onChange={(e) => setProspects(e.target.value)}
                />
              </div>
              
              <button 
                type="submit"
                disabled={status === 'Starting...' || status.includes('Waking')}
                className="w-full py-3 px-4 bg-gradient-to-r from-indigo-500 to-cyan-500 hover:from-indigo-400 hover:to-cyan-400 hover:shadow-[0_0_20px_rgba(99,102,241,0.4)] transition-all rounded-lg font-semibold text-white tracking-wide shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Launch Campaign
              </button>
            </form>

            {taskId && (
              <div className="mt-6 p-4 bg-slate-950/50 border border-slate-800 rounded-lg border-l-4 border-l-emerald-500">
                <p className="text-xs text-slate-400 font-mono break-all">Task ID:<br/>{taskId}</p>
              </div>
            )}
          </div>

          {/* Live View */}
          <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl flex flex-col">
            <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
              <span className="p-2 bg-rose-500/20 text-rose-400 rounded-md shadow-inner">🔴</span>
              Live View Stream
            </h2>
            
            <div className="flex-1 bg-black rounded-lg border border-slate-800 overflow-hidden relative shadow-inner min-h-[400px] flex items-center justify-center group overflow-y-auto aspect-video">
              {liveStream ? (
                <img 
                  src={liveStream} 
                  alt="Agent Live Feed" 
                  className="w-full h-full object-contain"
                />
              ) : (
                <div className="text-center space-y-4">
                  <div className="inline-block animate-pulse p-4 rounded-full bg-slate-800">
                    <svg className="w-8 h-8 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <p className="text-slate-500 font-medium">Waiting for Playwright Signal...</p>
                </div>
              )}
              
              <div className="absolute top-4 right-4 px-3 py-1 bg-black/60 backdrop-blur-md text-xs font-mono rounded text-slate-300 border border-slate-700/50 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity">
                WS: ACTIVE | LATENCY: &lt;50ms
              </div>
            </div>
            
          </div>
        </div>
      </div>
    </div>
  )
}
