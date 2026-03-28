import React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

const ChoicePage = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const selectedAlternative = location.state?.product
  const baseProduct = location.state?.baseProduct
  const comparison = location.state?.comparison

  const handleSave = () => {
    // Calculate points based on selected alternative score
    const pointsGathered = selectedAlternative.product_score || 50
    navigate('/success', { 
      state: { 
        chosenProduct: selectedAlternative,
        pointsGathered,
        baseProduct,
        comparison
      } 
    })
  }

  const handleDiscard = () => {
    navigate('/home')
  }

  if (!selectedAlternative) {
    return (
      <main className="min-h-screen bg-gray-50 p-4 sm:p-8">
        <div className="mx-auto max-w-md flex flex-col items-center justify-center min-h-screen">
          <div className="text-center">
            <p className="mb-4 text-[var(--color-primary)]">Nessun prodotto selezionato.</p>
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

  const productName = selectedAlternative.candidate_product_name || selectedAlternative.suggestion || 'Alternativa'

  return (
    <main className="min-h-screen bg-gray-50 p-4 sm:p-8">
      <div className="mx-auto max-w-md flex flex-col items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="mb-4 text-3xl font-bold text-[var(--color-green)]">
            Ottima scelta!
          </h1>
          <p className="mb-4 text-lg text-[var(--color-primary)]">
            {productName}
          </p>
          {selectedAlternative.candidate_brand && (
            <p className="mb-8 text-sm text-[var(--color-green)]">
              {selectedAlternative.candidate_brand}
            </p>
          )}

          {comparison && comparison.co2e_delta_kg_per_kg !== null && (
            <div className="mb-8 rounded-2xl bg-white p-4 border-2 border-[var(--color-green)]">
              <p className="text-xs font-semibold text-[var(--color-primary)] mb-2">
                Risparmio di CO\u2082
              </p>
              <p className="text-2xl font-bold text-[var(--color-lime)]">
                ~{(comparison.co2e_delta_kg_per_kg * 1000).toFixed(0)}g
              </p>
              <p className="text-xs text-[var(--color-primary)] mt-2">
                per porzione
              </p>
            </div>
          )}

          <p className="mb-12 text-lg text-[var(--color-primary)]">
            Vuoi salvare questa alternativa?
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
