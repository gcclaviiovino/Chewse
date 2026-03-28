import React, { useState, useRef, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'

const ChatbotPage = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const productData = location.state?.product

  const [messages, setMessages] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [alternatives, setAlternatives] = useState(null)
  const [preferenceSource, setPreferenceSource] = useState(null)
  const [needsFirstInput, setNeedsFirstInput] = useState(false)
  const messagesEndRef = useRef(null)
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const userId = 'mvp-default-user'

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Fetch initial alternatives when component mounts
  useEffect(() => {
    if (!productData?.barcode) {
      setMessages([
        {
          id: 1,
          text: 'Non riesco a leggere il barcode di questo prodotto. Riprova la scansione inquadrando bene il codice a barre.',
          sender: 'bot'
        }
      ])
      setIsLoading(false)
      return
    }

    const initializeChat = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/alternatives/from-barcode`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            barcode: productData.barcode,
            locale: 'it-IT',
            user_id: userId,
          }),
        })

        if (!response.ok) throw new Error('Failed to fetch alternatives')
        const data = await response.json()
        setAlternatives(data)
        setPreferenceSource(data.preference_source)

        const botMessage = {
          id: 1,
          text: data.assistant_message || 'Perfetto! Ecco le alternative disponibili.',
          sender: 'bot'
        }
        setMessages([botMessage])
        setNeedsFirstInput(data.needs_preference_input)
      } catch (error) {
        console.error('Error fetching alternatives:', error)
        setMessages([{ id: 1, text: 'Errore nella comunicazione con il server.', sender: 'bot' }])
      } finally {
        setIsLoading(false)
      }
    }

    initializeChat()
  }, [productData, apiBaseUrl])

  const handleSendMessage = async () => {
    if (inputValue.trim() === '') return

    const userMessage = { id: messages.length + 1, text: inputValue, sender: 'user' }
    setMessages([...messages, userMessage])
    setInputValue('')

    if (!needsFirstInput) {
      // Preferences already collected, show alternatives
      return
    }

    setIsLoading(true)
    try {
      const response = await fetch(`${apiBaseUrl}/alternatives/from-barcode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          barcode: productData.barcode,
          locale: 'it-IT',
          user_id: userId,
          user_message: inputValue,
        }),
      })

      if (!response.ok) throw new Error('Failed to process preferences')
      const data = await response.json()
      setAlternatives(data)
      setPreferenceSource(data.preference_source)
      setNeedsFirstInput(false)

      const botMessage = {
        id: messages.length + 2,
        text: data.assistant_message || 'Perfetto! Ho salvato le tue preferenze. Ecco le alternative disponibili.',
        sender: 'bot'
      }
      setMessages(prev => [...prev, botMessage])
    } catch (error) {
      console.error('Error processing preferences:', error)
      const errorMessage = {
        id: messages.length + 2,
        text: 'Errore nell\'elaborazione delle tue preferenze. Riprova.',
        sender: 'bot'
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleAcceptAlternative = () => {
    if (alternatives?.selected_candidate) {
      navigate('/choice', {
        state: {
          product: alternatives.selected_candidate.suggestion,
          baseProduct: productData,
          comparison: alternatives.impact_comparison
        }
      })
    }
  }

  if (!productData) {
    return (
      <main className="min-h-screen flex flex-col bg-gray-50">
        <div className="flex items-center justify-between bg-[var(--color-green)] px-6 py-4 text-white shadow-lg">
          <h1 className="text-xl font-semibold">Errore</h1>
          <button onClick={() => navigate('/home')} className="text-2xl font-bold hover:opacity-80 transition">✕</button>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center">
            <p className="text-[var(--color-primary)] mb-4">Nessun prodotto disponibile.</p>
            <button
              onClick={() => navigate('/home')}
              className="rounded-full bg-[var(--color-green)] px-6 py-3 font-semibold text-white transition hover:bg-[var(--color-primary)]"
            >
              Torna alla home
            </button>
          </div>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <div className="flex items-center justify-between bg-[var(--color-green)] px-6 py-4 text-white shadow-lg">
        <h1 className="text-xl font-semibold">Assistente Alternativa</h1>
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
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white border-2 border-[var(--color-green)] rounded-2xl px-4 py-3">
              <p className="text-sm text-[var(--color-primary)]">Sto elaborando...</p>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Alternatives Display */}
      {!needsFirstInput && alternatives && alternatives.candidates && alternatives.candidates.length > 0 && (
        <div className="border-t border-gray-200 bg-white p-4 shadow-lg">
          <div className="mx-auto max-w-md space-y-3">
            <h3 className="text-sm font-semibold text-[var(--color-green)]">Alternative disponibili:</h3>
            {alternatives.candidates.slice(0, 2).map((candidate, index) => (
              <div key={index} className="border-2 border-[var(--color-green)] rounded-2xl p-3 bg-gray-50">
                <p className="text-xs font-bold text-[var(--color-primary)] mb-1">
                  {candidate.suggestion.candidate_product_name || 'Alternativa'}
                </p>
                {candidate.suggestion.candidate_brand && (
                  <p className="text-xs text-[var(--color-green)] mb-2">{candidate.suggestion.candidate_brand}</p>
                )}
                {candidate.suggestion.eco_improvement_score !== null && (
                  <p className="text-xs text-[var(--color-primary)] mb-2">
                    Eco: +{(candidate.suggestion.eco_improvement_score * 100).toFixed(0)}%
                  </p>
                )}
                {!candidate.is_preference_compatible && (
                  <p className="text-xs text-red-600 mb-2">⚠️ Non in linea con preferenze</p>
                )}
              </div>
            ))}
            {alternatives.selected_candidate && (
              <button
                onClick={handleAcceptAlternative}
                className="w-full rounded-full bg-[var(--color-green)] px-4 py-3 font-semibold text-white transition hover:bg-[var(--color-primary)] text-sm"
              >
                Accetta alternativa consigliata
              </button>
            )}
          </div>
        </div>
      )}

      {/* Input Area */}
      {needsFirstInput && (
        <div className="border-t border-gray-200 bg-white p-4 shadow-lg">
          <div className="mx-auto max-w-md flex gap-3">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Es. vegano, no lattosio, senza plastica..."
              disabled={isLoading}
              className="flex-1 rounded-full border-2 border-[var(--color-green)] bg-transparent px-4 py-3 text-sm outline-none transition focus:border-[var(--color-lime)] disabled:opacity-50"
            />
            <button
              onClick={handleSendMessage}
              disabled={inputValue.trim() === '' || isLoading}
              className="rounded-full bg-[var(--color-green)] px-6 py-3 font-semibold text-white transition hover:bg-[var(--color-primary)] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Invia
            </button>
          </div>
        </div>
      )}
    </main>
  )
}

export default ChatbotPage
