/// <reference types="chrome" />
import { useState } from 'react'
import './App.css'

function App() {
  const [status, setStatus] = useState<string>('')
  const [error, setError] = useState<string>('')

  const syncCookies = async () => {
    try {
      setStatus('Fetching cookies...')
      setError('')

      // In Chrome extensions, chrome.cookies API is available if declared in manifest
      if (!chrome?.cookies) {
        throw new Error('chrome.cookies API is not available. Ensure you are running as an extension.')
      }

      // Get li_at
      const liAtCookie = await chrome.cookies.get({ url: 'https://www.linkedin.com', name: 'li_at' })
      const jsessionIdCookie = await chrome.cookies.get({ url: 'https://www.linkedin.com', name: 'JSESSIONID' })

      if (!liAtCookie?.value) {
        throw new Error('LinkedIn li_at cookie not found. Please log in to LinkedIn first.')
      }
      
      if (!jsessionIdCookie?.value) {
        throw new Error('LinkedIn JSESSIONID cookie not found.')
      }

      // Clean JSESSIONID value (sometimes it's wrapped in quotes)
      const jsessionId = jsessionIdCookie.value.replace(/"/g, '')

      setStatus('Syncing to Ghost-OS...')

      const response = await fetch('http://localhost:3000/api/sync-session', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          li_at: liAtCookie.value,
          JSESSIONID: jsessionId
        })
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Failed to sync with dashboard')
      }

      setStatus('✅ Successfully synced session!')
    } catch (err: any) {
      console.error(err)
      setError(err.message)
      setStatus('')
    }
  }

  return (
    <div style={{ padding: '20px', minWidth: '300px', textAlign: 'center' }}>
      <h2>👻 Ghost-OS</h2>
      <p>Click below to sync your active LinkedIn session to the Ghost-OS Dashboard.</p>
      
      <button 
        onClick={syncCookies}
        style={{ padding: '10px 20px', fontSize: '16px', cursor: 'pointer', backgroundColor: '#0070f3', color: 'white', border: 'none', borderRadius: '5px' }}
      >
        Sync Session
      </button>

      {status && <p style={{ color: 'green', marginTop: '15px' }}>{status}</p>}
      {error && <p style={{ color: 'red', marginTop: '15px' }}>{error}</p>}
    </div>
  )
}

export default App
