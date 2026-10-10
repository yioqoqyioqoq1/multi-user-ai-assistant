import { useCallback, useEffect, useRef, useState } from 'react'
import {
  api,
  chatSocketUrl,
  type ChatEvent,
  type Conversation,
  type Message,
  type Todo,
} from '../lib/api'

const todoText = (t: Todo): string =>
  typeof t === 'string' ? t : (t.content ?? JSON.stringify(t))

export default function ChatPage({ onLogout }: { onLogout: () => void }) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [history, setHistory] = useState<Message[]>([])
  const [paused, setPaused] = useState(false)
  const [todos, setTodos] = useState<Todo[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const wsRef = useRef<WebSocket | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const refreshList = useCallback(async () => {
    setConversations(await api.listConversations())
  }, [])

  const closeSocket = useCallback(() => {
    wsRef.current?.close()
    wsRef.current = null
  }, [])

  const connect = useCallback(
    (id: string) => {
      closeSocket()
      const ws = new WebSocket(chatSocketUrl(id))
      wsRef.current = ws
      ws.onmessage = (ev) => {
        let event: ChatEvent
        try {
          event = JSON.parse(ev.data) as ChatEvent
        } catch {
          return
        }
        switch (event.type) {
          case 'todos':
            setTodos(event.todos)
            break
          case 'approval':
            setHistory(event.history)
            setPaused(true)
            setLoading(false)
            break
          case 'final':
            setHistory(event.history)
            setPaused(false)
            setLoading(false)
            void refreshList()
            break
          case 'error':
            setError(event.detail)
            setLoading(false)
            break
        }
      }
      ws.onerror = () => setError('WebSocket 连接错误')
      ws.onclose = () => setLoading(false)
    },
    [closeSocket, refreshList],
  )

  useEffect(() => {
    refreshList().catch((e) => setError(e instanceof Error ? e.message : String(e)))
  }, [refreshList])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history, todos])

  useEffect(() => () => closeSocket(), [closeSocket])

  const select = async (id: string) => {
    setActiveId(id)
    setError('')
    setPaused(false)
    setTodos([])
    setLoading(false)
    try {
      setHistory((await api.getHistory(id)).history)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    connect(id)
  }

  const newConversation = async () => {
    setError('')
    try {
      const conv = await api.createConversation()
      await refreshList()
      setActiveId(conv.id)
      setHistory([])
      setPaused(false)
      setTodos([])
      setLoading(false)
      connect(conv.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const removeConversation = async (id: string) => {
    setError('')
    try {
      await api.deleteConversation(id)
      if (activeId === id) {
        closeSocket()
        setActiveId(null)
        setHistory([])
        setTodos([])
        setPaused(false)
      }
      await refreshList()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const send = () => {
    const msg = input.trim()
    const ws = wsRef.current
    if (!activeId || !msg || loading) return
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setError('连接未就绪，请稍后再试')
      return
    }
    setError('')
    setLoading(true)
    setTodos([])
    const current = history
    setHistory([...current, { role: 'user', content: msg }])
    ws.send(JSON.stringify({ type: 'turn', message: msg, success_criteria: '', history: current }))
    setInput('')
  }

  const approve = () => {
    const ws = wsRef.current
    if (!activeId || loading) return
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setError('连接未就绪，请稍后再试')
      return
    }
    setError('')
    setLoading(true)
    ws.send(JSON.stringify({ type: 'approve', history }))
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

        {todos.length > 0 && (
          <div className="border-b border-gray-200 bg-indigo-50 px-6 py-3">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-indigo-700">
              待办
            </h3>
            <ul className="space-y-1">
              {todos.map((t, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-400" />
                  <span className="whitespace-pre-wrap">{todoText(t)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {activeId ? (
          <>
            <div className="flex-1 overflow-y-auto px-6 py-4">
              {history.length === 0 && !loading && (
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
              {loading && (
                <div className="mb-3 flex justify-start">
                  <div className="rounded-xl bg-white px-4 py-2 text-sm text-gray-400 shadow">
                    处理中…
                  </div>
                </div>
              )}
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