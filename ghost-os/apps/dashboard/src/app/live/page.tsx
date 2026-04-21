'use client'

import { useState, useEffect, useRef } from 'react'
import { wsUrl, getAccountId } from '../../lib/api'

export default function LivePage() {
  const [liveStream, setLiveStream] = useState<string | null>(null)
  const [status, setStatus] = useState('Connecting...')
  const [isManualMode, setIsManualMode] = useState(false)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const imageRef = useRef<HTMLImageElement>(null)
  const accountId = getAccountId()

  useEffect(() => {
    const url = accountId ? wsUrl(`/ws/live/${accountId}`) : wsUrl('/ws/agent')

    const connect = () => {
      const ws = new WebSocket(url)

      ws.onopen = () => {
        setConnected(true)
        setStatus('Waiting for agent...')
        wsRef.current = ws
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'screen') {
            setLiveStream(`data:image/jpeg;base64,${msg.data}`)
            if (status === 'Waiting for agent...') setStatus('Live')
          } else if (msg.type === 'status') {
            if (msg.data === 'manual_login_required') {
              setIsManualMode(true)
              setStatus('Manual Login Required')
            } else if (msg.data === 'running') {
              setIsManualMode(false)
              setStatus('Live')
            }
          }
        } catch (e) {
          console.error('WS parse error:', e)
        }
      }

      ws.onclose = () => {
        setConnected(false)
        setStatus('Reconnecting...')
        wsRef.current = null
        setTimeout(connect, 3000)
      }

      ws.onerror = () => ws.close()
    }

    connect()
    return () => wsRef.current?.close()
  }, [accountId])

  const handleImageClick = (e: React.MouseEvent<HTMLImageElement>) => {
    if (!isManualMode || !imageRef.current || !wsRef.current) return
    const rect = imageRef.current.getBoundingClientRect()
    const scaleX = imageRef.current.naturalWidth / rect.width
    const scaleY = imageRef.current.naturalHeight / rect.height
    wsRef.current.send(JSON.stringify({
      type: 'click',
      x: Math.round((e.clientX - rect.left) * scaleX),
      y: Math.round((e.clientY - rect.top) * scaleY),
    }))
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isManualMode || !wsRef.current) return
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space', 'Tab', 'Enter'].includes(e.code)) {
      e.preventDefault()
    }
    wsRef.current.send(JSON.stringify({ type: 'key', key: e.key }))
  }

  return (
    <div className="p-8 space-y-4 max-w-6xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Live View</h1>
          <p className="text-slate-400 text-sm mt-1">Real-time agent browser stream</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}`} />
          <span className="text-sm text-slate-400">{status}</span>
        </div>
      </div>

      <div
        className={`bg-black rounded-xl border overflow-hidden min-h-[600px] flex items-center justify-center relative aspect-video cursor-crosshair outline-none ${
          isManualMode ? 'border-amber-500 shadow-[0_0_30px_rgba(245,158,11,0.3)]' : 'border-slate-800'
        }`}
        tabIndex={0}
        onKeyDown={handleKeyDown}
      >
        {liveStream ? (
          <img
            ref={imageRef}
            src={liveStream}
            alt="Agent Live Feed"
            className="w-full h-full object-fill"
            onClick={handleImageClick}
          />
        ) : (
          <div className="text-center space-y-3">
            <div className="inline-block animate-pulse p-5 rounded-full bg-slate-900">
              <svg className="w-10 h-10 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </div>
            <p className="text-slate-600 font-medium">Waiting for agent signal...</p>
            <p className="text-slate-700 text-sm">Start the agent from Overview to see the live stream</p>
          </div>
        )}

        {isManualMode && (
          <div className="absolute inset-0 bg-amber-500/5 pointer-events-none flex items-start justify-center pt-4">
            <div className="px-4 py-2 bg-amber-600 text-white text-sm font-bold rounded-full shadow-lg animate-bounce">
              ⚠️ MANUAL LOGIN — CLICK TO INTERACT
            </div>
          </div>
        )}

        <div className="absolute bottom-3 right-3 px-2 py-1 bg-black/70 text-xs font-mono rounded text-slate-500 border border-slate-800">
          {connected ? '● LIVE' : '○ OFFLINE'} {isManualMode ? '| INTERACTIVE' : ''}
        </div>
      </div>

      <p className="text-xs text-slate-600 text-center">
        When in manual mode, click anywhere on the browser to interact · Use keyboard for typing
      </p>
    </div>
  )
}
