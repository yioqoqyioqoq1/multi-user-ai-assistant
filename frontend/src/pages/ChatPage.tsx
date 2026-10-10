import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Conversation, type Message } from '../lib/api'

export default function ChatPage({ onLogout }: { onLogout: () => void }) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [history, setHistory] = useState<Message[]>([])
  const [paused, setPaused] = useState(false)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const refreshList = useCallback(async () => {
    setConversations(await api.listConversations())
  }, [])

  useEffect(() => {
    refreshList().catch((e) => setError(e instanceof Error ? e.message : String(e)))
  }, [refreshList])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  const select = async (id: string) => {
    setActiveId(id)
    setError('')
    try {
      setHistory((await api.getHistory(id)).history)
      setPaused(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const newConversation = async () => {
    setError('')
    try {
      const conv = await api.createConversation()
      await refreshList()
      setActiveId(conv.id)
      setHistory([])
      setPaused(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const removeConversation = async (id: string) => {
    setError('')
    try {
      await api.deleteConversation(id)
      if (activeId === id) {
        setActiveId(null)
        setHistory([])
      }
      await refreshList()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const send = async () => {
    if (!activeId || !input.trim() || loading) return
    setError('')
    setLoading(true)
    try {
      const res = await api.runTurn(activeId, input.trim())
      setHistory(res.history)
      setPaused(res.paused)
      setInput('')
      await refreshList()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const approve = async () => {
    if (!activeId || loading) return
    setError('')
    setLoading(true)
    try {
      const res = await api.approve(activeId)
      setHistory(res.history)
      setPaused(res.paused)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen bg-gray-100 text-gray-800">
      {/* 侧边栏：会话列表 */}
      <aside className="flex w-64 shrink-0 flex-col border-r border-gray-200 bg-white">
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
          <span className="font-semibold">会话</span>
          <button
            type="button"
            onClick={onLogout}
            className="text-sm text-gray-500 hover:text-gray-800"
          >
            退出
          </button>
        </div>
        <button
          type="button"
          onClick={newConversation}
          className="m-3 rounded-lg bg-indigo-600 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          + 新建会话
        </button>
        <nav className="flex-1 overflow-y-auto px-2">
          {conversations.map((c) => (
            <div
              key={c.id}
              onClick={() => select(c.id)}
              className={`group mb-1 flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm ${
                activeId === c.id ? 'bg-indigo-50 text-indigo-700' : 'hover:bg-gray-100'
              }`}
            >
              <span className="truncate">{c.title}</span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  removeConversation(c.id)
                }}
                className="ml-2 hidden text-gray-400 hover:text-red-600 group-hover:block"
              >
                ×
              </button>
            </div>
          ))}
        </nav>
      </aside>

      {/* 主聊天区 */}
      <main className="flex flex-1 flex-col">
        {error && (
          <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        {activeId ? (
          <>
            <div className="flex-1 overflow-y-auto px-6 py-4">
              {history.length === 0 && (
                <p className="text-center text-gray-400">开始对话吧</p>
              )}
              {history.map((m, i) => {
                const isUser = m.role === 'user'
                return (
                  <div
                    key={i}
                    className={`mb-3 flex ${isUser ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[75%] whitespace-pre-wrap rounded-xl px-4 py-2 text-sm ${
                        isUser ? 'bg-indigo-600 text-white' : 'bg-white text-gray-800 shadow'
                      }`}
                    >
                      {m.content}
                    </div>
                  </div>
                )
              })}
              <div ref={bottomRef} />
            </div>

            <div className="border-t border-gray-200 bg-white p-4">
              {paused && (
                <button
                  type="button"
                  onClick={approve}
                  disabled={loading}
                  className="mb-3 rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50"
                >
                  批准待处理操作
                </button>
              )}
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  send()
                }}
                className="flex gap-3"
              >
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="输入任务…"
                  disabled={loading}
                  className="flex-1 rounded-lg border border-gray-300 px-4 py-2 outline-none focus:border-indigo-500"
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="rounded-lg bg-indigo-600 px-5 py-2 font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  {loading ? '处理中…' : '发送'}
                </button>
              </form>
            </div>
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center text-gray-400">
            选择或新建一个会话
          </div>
        )}
      </main>
    </div>
  )
}