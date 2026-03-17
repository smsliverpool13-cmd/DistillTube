'use client'

import { useEffect, useState, useRef } from 'react'
import { Send, Menu, X, ChevronDown, ChevronRight, Plus, LogOut } from 'lucide-react'
import Image from 'next/image'
import { supabase } from '@/lib/supabase'

const loadingSteps = [
  "Fetching video...",
  "Extracting transcript...",
  "Generating embeddings...",
  "Distilling insights...",
  "Ready",
]

function formatTime(timestamp: any): string {
  if (typeof timestamp === 'string' && timestamp.includes(':')) return timestamp
  const secs = typeof timestamp === 'number' ? timestamp : parseFloat(timestamp)
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days === 1) return 'Yesterday'
  return `${days} days ago`
}

export default function DistillTube() {
  const [session, setSession] = useState<any>(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [videoLoaded, setVideoLoaded] = useState(false)
  const [loadingStep, setLoadingStep] = useState(-1)
  const [transcriptOpen, setTranscriptOpen] = useState(true)
  const [summaryOpen, setSummaryOpen] = useState(true)
  const [currentVideo, setCurrentVideo] = useState<any>(null)
  const [transcript, setTranscript] = useState<any[]>([])
  const [summary, setSummary] = useState<any>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [recentVideos, setRecentVideos] = useState<any[]>([])
  const [messages, setMessages] = useState<any[]>([])
  const [inputValue, setInputValue] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [activeVideoId, setActiveVideoId] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  const delay = (ms: number) => new Promise(r => setTimeout(r, ms))

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setIsAuthenticated(!!session)
      if (session) loadRecentVideos(session.access_token)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      setIsAuthenticated(!!session)
      if (session) loadRecentVideos(session.access_token)
    })

    return () => subscription.unsubscribe()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleLogin = async () => {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin }
    })
  }

  const handleLogout = async () => {
    await supabase.auth.signOut()
    setIsAuthenticated(false)
    setSession(null)
    setVideoLoaded(false)
    setCurrentVideo(null)
    setRecentVideos([])
  }

  const loadRecentVideos = async (token: string) => {
    try {
      const res = await fetch(`${API}/videos`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      const data = await res.json()
      setRecentVideos(data.videos || [])
    } catch (err) {
      console.error('Failed to load recent videos:', err)
    }
  }

  const handleSubmitUrl = async () => {
    if (!inputValue.trim() || !session?.access_token) return
    const token = session.access_token
    const url = inputValue.trim()

    setLoadingStep(0)

    // Advance steps visually on timer regardless of API
    const stepTimer1 = setTimeout(() => setLoadingStep(1), 2000)
    const stepTimer2 = setTimeout(() => setLoadingStep(2), 4000)
    const stepTimer3 = setTimeout(() => setLoadingStep(3), 6000)

    try {
      const res = await fetch(`${API}/transcript`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ url })
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to fetch transcript')
      }
      const data = await res.json()

      // Clear timers, jump to final step
      clearTimeout(stepTimer1)
      clearTimeout(stepTimer2)
      clearTimeout(stepTimer3)
      setLoadingStep(4)

      await delay(600)

      setCurrentVideo({
        id: data.video_id,
        title: data.title,
        channel: data.channel || '',
        duration: data.duration,
        thumbnail: `https://img.youtube.com/vi/${data.video_id}/mqdefault.jpg`
      })
      setTranscript(data.segments || [])
      setActiveVideoId(data.video_id)
      setMessages([])
      setSummary(null)
      setInputValue('')
      setVideoLoaded(true)
      setLoadingStep(-1)
      loadRecentVideos(token)

    } catch (err: any) {
      clearTimeout(stepTimer1)
      clearTimeout(stepTimer2)
      clearTimeout(stepTimer3)
      setLoadingStep(-1)
      alert(err.message || 'Could not process video. Check the URL and try again.')
    }
  }

  const handleLoadRecent = async (videoId: string) => {
    const token = session?.access_token
    if (!token) return

    try {
      const res = await fetch(`${API}/transcript/${videoId}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      const data = await res.json()

      setCurrentVideo({
        id: videoId,
        title: data.title,
        channel: data.channel || '',
        thumbnail: `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`
      })
      setTranscript(data.segments || [])
      setActiveVideoId(videoId)
      setMessages([])
      setSummary(null)
      setVideoLoaded(true)
    } catch (err) {
      console.error('Failed to load recent:', err)
    }
  }

  const handleGenerateSummary = async () => {
    if (!currentVideo?.id || !session?.access_token) return
    setSummaryLoading(true)
    try {
      const res = await fetch(`${API}/summary`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.access_token}`
        },
        body: JSON.stringify({ video_id: currentVideo.id })
      })
      const data = await res.json()
      setSummary(data)
    } catch (err) {
      console.error('Summary error:', err)
    } finally {
      setSummaryLoading(false)
    }
  }

  const handleSendMessage = async () => {
    if (!inputValue.trim() || !currentVideo?.id || !session?.access_token) return

    const question = inputValue.trim()
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'user',
      content: question
    }])
    setInputValue('')
    setChatLoading(true)

    try {
      const res = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.access_token}`
        },
        body: JSON.stringify({
          video_id: currentVideo.id,
          question,
          chat_history: []
        })
      })
      const data = await res.json()

      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.answer,
        sources: data.sources?.map((s: any) => formatTime(s.start_time)) || []
      }])
    } catch (err) {
      console.error('Chat error:', err)
    } finally {
      setChatLoading(false)
    }
  }

  const handleNewChat = () => {
    setVideoLoaded(false)
    setCurrentVideo(null)
    setTranscript([])
    setMessages([])
    setSummary(null)
    setInputValue('')
    setActiveVideoId('')
    setLoadingStep(-1)
  }

  // Login screen
  if (!isAuthenticated) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-[#13111e]">
        <div className="flex flex-col items-center w-full max-w-sm px-6">

          {/* Logo + Title tight together */}
          <img src="/logo.png" alt="DistillTube" className="w-32 h-32 mb-[-9px]" />
          <h1 className="text-3xl font-bold text-white mb-1">DistillTube</h1>
          <p className="text-[#8b8a9b] text-sm mb-8">Watch less. Understand more.</p>

          {/* Google button */}
          <button
            onClick={handleLogin}
            className="w-full flex items-center justify-center gap-3 bg-white text-gray-800 font-medium rounded-xl px-4 py-3 hover:bg-gray-100 transition-all"
          >
            <svg width="18" height="18" viewBox="0 0 18 18">
              <path fill="#4285F4" d="M16.51 8H8.98v3h4.3c-.18 1-.74 1.48-1.6 2.04v2.01h2.6a7.8 7.8 0 0 0 2.38-5.88c0-.57-.05-.66-.15-1.18z"/>
              <path fill="#34A853" d="M8.98 17c2.16 0 3.97-.72 5.3-1.94l-2.6-2a4.8 4.8 0 0 1-7.18-2.54H1.83v2.07A8 8 0 0 0 8.98 17z"/>
              <path fill="#FBBC05" d="M4.5 10.52a4.8 4.8 0 0 1 0-3.04V5.41H1.83a8 8 0 0 0 0 7.18l2.67-2.07z"/>
              <path fill="#EA4335" d="M8.98 4.18c1.17 0 2.23.4 3.06 1.2l2.3-2.3A8 8 0 0 0 1.83 5.4L4.5 7.49a4.77 4.77 0 0 1 4.48-3.3z"/>
            </svg>
            Continue with Google
          </button>

          <p className="text-[#8b8a9b] text-xs mt-4">Free to use · No credit card required</p>
        </div>
      </div>
    )
  }

  const isLoading = loadingStep >= 0
  const userEmail = session?.user?.email || ''
  const userInitials = userEmail.slice(0, 2).toUpperCase()

  return (
    <div className="flex h-screen w-full bg-[#13111e] text-white">
      {/* Sidebar */}
      <div
        className={`flex flex-col border-r border-[#2d2a3e] bg-[#1a1727] transition-all duration-300 ${
          sidebarOpen ? 'w-64' : 'w-0 overflow-hidden'
        }`}
      >
        {sidebarOpen && (
          <>
            {/* Logo */}
            <div className="border-b border-[#2d2a3e] px-4 py-4">
              <div className="flex items-center gap-2">
                <Image
                  src="/logo.png"
                  alt="Logo"
                  width={48}
                  height={48}
                />
                <span className="font-bold text-white">DistillTube</span>
              </div>
            </div>

            {/* New Chat Button */}
            <div className="border-b border-[#2d2a3e] px-4 py-4">
              <button
                onClick={handleNewChat}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#7c6af7] px-4 py-2 font-medium text-white transition-all hover:bg-[#6c5fe8]"
              >
                <Plus size={20} />
                New Chat
              </button>
            </div>

            {/* Recent Videos */}
            <div className="flex-1 overflow-y-auto px-4 py-4">
              <p className="text-xs font-semibold text-gray-400 uppercase">Recent</p>
              <div className="mt-2" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {recentVideos.map((video) => (
                  <div
                    key={video.video_id}
                    onClick={() => handleLoadRecent(video.video_id)}
                    className="cursor-pointer rounded-lg px-2 pt-2 pb-2 transition-colors"
                    style={{
                      backgroundColor: activeVideoId === video.video_id ? '#1f1c2e' : 'transparent',
                      borderLeft: activeVideoId === video.video_id ? '2px solid #7c6af7' : '2px solid transparent',
                    }}
                    onMouseEnter={(e) => {
                      if (activeVideoId !== video.video_id) {
                        (e.currentTarget as HTMLDivElement).style.backgroundColor = '#252235'
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (activeVideoId !== video.video_id) {
                        (e.currentTarget as HTMLDivElement).style.backgroundColor = 'transparent'
                      }
                    }}
                  >
                    <img
                      src={`https://img.youtube.com/vi/${video.video_id}/mqdefault.jpg`}
                      alt={video.title}
                      className="w-full rounded-lg object-cover"
                      style={{ height: '56px' }}
                    />
                    <p className="mt-1.5 text-sm font-medium text-white truncate">{video.title}</p>
                    <p className="text-xs" style={{ color: '#8b8a9b' }}>{relativeTime(video.created_at)}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* User Profile */}
            <div className="border-t border-[#2d2a3e] px-4 py-4">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-full bg-[#7c6af7] flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                  {userInitials}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{userEmail}</p>
                  <p className="text-xs text-[#8b8a9b]">Free Plan</p>
                  <button className="text-xs text-[#7c6af7] font-medium hover:underline">Upgrade →</button>
                </div>
                <button
                  onClick={handleLogout}
                  className="p-1.5 rounded-lg hover:bg-[#2d2a3e] text-[#8b8a9b] hover:text-white"
                >
                  <LogOut size={16} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Main Content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#2d2a3e] bg-[#1f1c2e] px-6 py-4">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="rounded-lg p-2 hover:bg-[#2d2a3e]"
          >
            {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
          <h1 className="text-xl font-semibold">DistillTube</h1>
          <div className="w-10" />
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-hidden flex">

          {/* Left: Transcript — only when videoLoaded */}
          {videoLoaded && transcriptOpen && (
            <div className="w-[35%] flex flex-col border-r border-[#2d2a3e] bg-[#1a1727] transition-all duration-300 flex-shrink-0">
              <div className="border-b border-[#2d2a3e] px-6 py-3 flex items-center justify-between">
                <h3 className="font-semibold">Transcript</h3>
                <button
                  onClick={() => setTranscriptOpen(false)}
                  className="rounded p-1 hover:bg-[#2d2a3e] text-gray-400 hover:text-white"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
                {transcript.map((segment, index) => (
                  <div key={index} className="text-sm">
                    <div className="text-xs font-medium text-[#7c6af7]">
                      {segment.start != null ? formatTime(segment.start) : segment.time || ''}
                    </div>
                    <div className="text-gray-300 text-xs leading-relaxed">{segment.text}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Collapsed transcript expand tab */}
          {videoLoaded && !transcriptOpen && (
            <div className="flex flex-col border-r border-[#2d2a3e] bg-[#1a1727] items-center pt-4 w-8 flex-shrink-0">
              <button
                onClick={() => setTranscriptOpen(true)}
                className="rounded p-1 hover:bg-[#2d2a3e] text-gray-400 hover:text-white"
                title="Show transcript"
              >
                <ChevronRight size={16} style={{ transform: 'rotate(180deg)' }} />
              </button>
            </div>
          )}

          {/* Center: loading / empty state / video content */}
          {isLoading ? (
            <div className="flex-1 flex items-center justify-center flex-col gap-6 px-6">
              <div className="w-full max-w-sm space-y-5">
                <div className="space-y-3">
                  {loadingSteps.map((step, index) => {
                    const isDone = index < loadingStep
                    const isCurrent = index === loadingStep
                    const isPending = index > loadingStep
                    return (
                      <div
                        key={index}
                        className="flex items-center gap-3 text-sm transition-all duration-500"
                        style={{
                          color: isDone ? '#ffffff' : isCurrent ? '#7c6af7' : '#8b8a9b',
                          opacity: isPending ? 0.4 : 1,
                        }}
                      >
                        <span className={isCurrent ? 'font-medium' : ''}>{step}</span>
                      </div>
                    )
                  })}
                </div>
                {/* Progress bar */}
                <div
                  className="h-0.5 w-full rounded-full overflow-hidden"
                  style={{ backgroundColor: '#2d2a3e' }}
                >
                  <div
                    className="h-full rounded-full"
                    style={{
                      backgroundColor: '#7c6af7',
                      width: `${Math.min((loadingStep / loadingSteps.length) * 100, 100)}%`,
                      transition: 'width 0.8s ease',
                    }}
                  />
                </div>
              </div>
            </div>
          ) : !videoLoaded ? (
            <div className="flex-1 flex items-center justify-center flex-col px-6">
              <img src="/logo.png" alt="DistillTube" className="w-32 h-32 mb-[-9px]" />
              <h2 className="text-2xl font-bold text-white mb-1">Paste a YouTube link</h2>
              <p className="text-[#8b8a9b] text-sm mb-8">and let us distill the knowledge</p>
              <div className="w-full max-w-md space-y-3">
                <input
                  type="text"
                  placeholder="https://youtube.com/watch?v=..."
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSubmitUrl()}
                  className="w-full rounded-lg border border-[#2d2a3e] bg-[#1f1c2e] px-4 py-3 text-white placeholder-gray-500 focus:border-[#7c6af7] focus:outline-none"
                />
                <button
                  onClick={handleSubmitUrl}
                  disabled={!inputValue.trim()}
                  className={`w-full rounded-xl px-4 py-3 font-medium transition-all ${
                    inputValue.trim()
                      ? 'bg-[#7c6af7] text-white hover:bg-[#6b5ce6] cursor-pointer'
                      : 'bg-[#2d2a3e] text-[#8b8a9b] cursor-not-allowed'
                  }`}
                >
                  Generate Summary
                </button>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col bg-[#1f1c2e] overflow-hidden">
              {/* Video header with thumbnail */}
              <div className="border-b border-[#2d2a3e] bg-[#1a1727] px-6 py-4 flex items-center gap-4 flex-shrink-0">
                <img
                  src={currentVideo?.thumbnail}
                  alt={currentVideo?.title}
                  className="h-16 w-28 rounded-lg object-cover flex-shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold truncate">{currentVideo?.title}</h3>
                  <p className="text-xs text-gray-400">
                    {currentVideo?.channel}{currentVideo?.duration ? ` · ${currentVideo.duration}` : ''}
                  </p>
                </div>
              </div>

              {/* Summary (collapsible) */}
              {summaryOpen ? (
                <div className="border-b border-[#2d2a3e] max-h-64 overflow-y-auto flex-shrink-0">
                  <div className="flex items-center justify-between px-6 py-3 sticky top-0 bg-[#1f1c2e] z-10 border-b border-[#2d2a3e]">
                    <h4 className="font-semibold">Summary</h4>
                    <button
                      onClick={() => setSummaryOpen(false)}
                      className="rounded p-1 hover:bg-[#2d2a3e] text-gray-400 hover:text-white"
                    >
                      <ChevronDown size={20} />
                    </button>
                  </div>
                  <div className="px-6 py-4">

                  {summary === null && !summaryLoading && (
                    <button
                      onClick={handleGenerateSummary}
                      className="rounded-lg bg-[#7c6af7] px-4 py-2 text-sm font-medium text-white transition-all hover:bg-[#6c5fe8]"
                    >
                      ✨ Generate Summary
                    </button>
                  )}

                  {summaryLoading && (
                    <div className="flex items-center gap-2 text-sm text-gray-400">
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#7c6af7] border-t-transparent" />
                      Generating...
                    </div>
                  )}

                  {summary !== null && (
                    <>
                      <p className="text-sm text-gray-300 leading-relaxed">{summary.summary}</p>
                      {summary.key_moments?.length > 0 && (
                        <div className="mt-4">
                          <h5 className="text-xs font-semibold text-gray-400 uppercase">Key Moments</h5>
                          <div className="mt-2 space-y-2">
                            {summary.key_moments.map((km: any, index: number) => (
                              <div key={index} className="text-xs">
                                <span className="font-medium text-[#7c6af7]">{formatTime(km.timestamp)}</span>
                                <span className="ml-2 text-gray-400">{km.text}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {summary.topics?.length > 0 && (
                        <div className="mt-4">
                          <h5 className="text-xs font-semibold text-gray-400 uppercase">Topics</h5>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {summary.topics.map((topic: string, index: number) => (
                              <span
                                key={index}
                                className="rounded-full bg-[#2d2a3e] px-3 py-1 text-xs text-gray-300"
                              >
                                {topic}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                  </div>
                </div>
              ) : (
                <div className="border-b border-[#2d2a3e] px-6 py-2 flex items-center justify-between flex-shrink-0">
                  <h4 className="font-semibold text-sm">Summary</h4>
                  <button
                    onClick={() => setSummaryOpen(true)}
                    className="rounded p-1 hover:bg-[#2d2a3e] text-gray-400 hover:text-white"
                  >
                    <ChevronRight size={20} />
                  </button>
                </div>
              )}

              {/* Chat Area */}
              <div className="flex-1 flex flex-col overflow-hidden">
                <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
                  {messages.length === 0 && (
                    <div className="flex items-center justify-center h-full">
                      <p className="text-sm text-gray-500">Ask anything about this video...</p>
                    </div>
                  )}
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`rounded-lg px-4 py-2 max-w-xs text-sm ${
                          message.role === 'user'
                            ? 'bg-[#7c6af7] text-white'
                            : 'bg-[#2d2a3e] text-gray-300'
                        }`}
                      >
                        {message.content}
                        {message.sources?.length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {message.sources.map((src: string, i: number) => (
                              <span key={i} className="text-xs text-[#7c6af7] font-medium">[{src}]</span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  {chatLoading && (
                    <div className="flex justify-start">
                      <div className="rounded-lg px-4 py-2 bg-[#2d2a3e] text-gray-300 text-sm">
                        <span className="animate-pulse">...</span>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input */}
                <div className="border-t border-[#2d2a3e] bg-[#1a1727] px-6 py-4 flex-shrink-0">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Ask anything about this video..."
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                      className="flex-1 rounded-lg border border-[#2d2a3e] bg-[#1f1c2e] px-4 py-2 text-white placeholder-gray-500 focus:border-[#7c6af7] focus:outline-none text-sm"
                    />
                    <button
                      onClick={handleSendMessage}
                      className="rounded-lg bg-[#7c6af7] p-2 text-white transition-all hover:bg-[#6c5fe8]"
                    >
                      <Send size={20} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
