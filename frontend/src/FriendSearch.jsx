import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const FriendSearch = () => {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [message, setMessage] = useState('')
  const [isError, setIsError] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const handleAddFriend = async () => {
    if (!username.trim()) return

    setIsLoading(true)
    setMessage('')

    try {
      const response = await fetch('http://localhost:8000/api/add-friend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_user: 'alice123', // Usually comes from your Auth context
          friend_username: username
        })
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Something went wrong')
      }

      setMessage(data.message)
      setIsError(false)
      setUsername('') // Clear input on success
    } catch (err) {
      setMessage(err.message)
      setIsError(true)
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !isLoading) {
      handleAddFriend()
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 p-0">
      {/* Header */}
      <div className="flex items-center justify-between bg-[var(--color-green)] px-6 py-4 text-white shadow-lg">
        <h1 className="text-xl font-semibold">Aggiungi un amico</h1>
        <button
          onClick={() => navigate('/home')}
          className="text-2xl font-bold hover:opacity-80 transition"
        >
          ✕
        </button>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-md space-y-6 p-4">
        <div className="rounded-3xl border-2 border-[var(--color-green)] bg-white shadow-lg overflow-hidden">
          <div className="bg-[var(--color-green)] px-6 py-3 text-center text-white font-semibold">
            Cerca un amico
          </div>
          <div className="bg-[var(--color-cream)] px-6 py-8 space-y-4">
            <div>
              <label className="mb-3 block text-sm font-medium text-[var(--color-green)]">
                Nome utente
              </label>
              <input
                type="text"
                placeholder="Inserisci il nome utente..."
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={isLoading}
                className="w-full rounded-full border-2 border-[var(--color-green)] bg-white px-6 py-3 text-sm outline-none transition focus:border-[var(--color-lime)] disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>

            <button
              onClick={handleAddFriend}
              disabled={isLoading || !username.trim()}
              className="w-full rounded-full bg-[var(--color-green)] px-6 py-3 font-semibold text-white transition hover:bg-[var(--color-primary)] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'In corso...' : 'Aggiungi amico'}
            </button>

            {message && (
              <div
                className={`rounded-xl border-2 px-4 py-3 text-sm font-medium ${
                  isError
                    ? 'border-red-400 bg-red-50 text-red-700'
                    : 'border-[var(--color-lime)] bg-[var(--color-cream)] text-[var(--color-green)]'
                }`}
              >
                {message}
              </div>
            )}
          </div>
        </div>

        <button
          onClick={() => navigate('/home')}
          className="w-full rounded-full border-2 border-[var(--color-green)] bg-transparent px-6 py-3 font-semibold text-[var(--color-green)] transition hover:bg-gray-100"
        >
          Annulla
        </button>
      </div>
    </main>
  )
}

export default FriendSearch