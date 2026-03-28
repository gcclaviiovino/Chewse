import React, { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const ChatbotPage = () => {
  const navigate = useNavigate()
  const [messages, setMessages] = useState([
    { id: 1, text: 'Ciao! Come posso aiutarti?', sender: 'bot' }
  ])
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendMessage = () => {
    if (inputValue.trim() === '') return

    // Add user message
    const userMessage = { id: messages.length + 1, text: inputValue, sender: 'user' }
    setMessages([...messages, userMessage])
    setInputValue('')

    // Simulate bot response (will be replaced with actual agent later)
    setTimeout(() => {
      const botMessage = {
        id: messages.length + 2,
        text: 'Interessante! Puoi raccontarmi di più?',
        sender: 'bot'
      }
      setMessages(prev => [...prev, botMessage])
    }, 500)
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <main className="min-h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <div className="flex items-center justify-between bg-[var(--color-green)] px-6 py-4 text-white shadow-lg">
        <h1 className="text-xl font-semibold">Assistente</h1>
        <button
          onClick={() => navigate('/home')}
          className="text-2xl font-bold hover:opacity-80 transition"
        >
          ✕
        </button>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-xs rounded-2xl px-4 py-3 ${
                message.sender === 'user'
                  ? 'bg-[var(--color-lime)] text-black'
                  : 'bg-white border-2 border-[var(--color-green)] text-[var(--color-primary)]'
              }`}
            >
              <p className="text-sm">{message.text}</p>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 bg-white p-4 shadow-lg">
        <div className="mx-auto max-w-md flex gap-3">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Scrivi un messaggio..."
            className="flex-1 rounded-full border-2 border-[var(--color-green)] bg-transparent px-4 py-3 text-sm outline-none transition focus:border-[var(--color-lime)]"
          />
          <button
            onClick={handleSendMessage}
            disabled={inputValue.trim() === ''}
            className="rounded-full bg-[var(--color-green)] px-6 py-3 font-semibold text-white transition hover:bg-[var(--color-primary)] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Invia
          </button>
        </div>
      </div>
    </main>
  )
}

export default ChatbotPage
