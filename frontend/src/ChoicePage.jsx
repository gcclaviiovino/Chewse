import React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

const ChoicePage = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const product = location.state?.product

  const handleSave = () => {
    // TODO: Implement save product logic
    console.log('Save product:', product)
    navigate('/home')
  }

  const handleDiscard = () => {
    navigate('/home')
  }

  return (
    <main className="min-h-screen bg-gray-50 p-4 sm:p-8">
      <div className="mx-auto max-w-md flex flex-col items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="mb-8 text-3xl font-bold text-[var(--color-green)]">
            Ottima scelta!
          </h1>
          <p className="mb-12 text-lg text-[var(--color-primary)]">
            Vuoi salvare questo prodotto?
          </p>

          <div className="flex gap-3">
            <button
              onClick={handleSave}
              className="flex-1 rounded-full bg-[var(--color-green)] px-6 py-3 font-semibold text-white transition hover:bg-[var(--color-primary)]"
            >
              Salva
            </button>
            <button
              onClick={handleDiscard}
              className="flex-1 rounded-full border-2 border-[var(--color-green)] bg-transparent px-6 py-3 font-semibold text-[var(--color-green)] transition hover:bg-gray-100"
            >
              Scarta
            </button>
          </div>
        </div>
      </div>
    </main>
  )
}

export default ChoicePage
