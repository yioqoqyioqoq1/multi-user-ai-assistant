import { useState } from 'react'
import { clearToken, getToken } from './lib/api'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'

function App() {
  const [authed, setAuthed] = useState<boolean>(() => !!getToken())

  return authed ? (
    <ChatPage
      onLogout={() => {
        clearToken()
        setAuthed(false)
      }}
    />
  ) : (
    <LoginPage onLogin={() => setAuthed(true)} />
  )
}

export default App