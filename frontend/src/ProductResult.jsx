import React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ProductDisplay from './ProductDisplay'

const ProductResult = () => {
  const navigate = useNavigate()
  const location = useLocation()

  const productData = location.state?.product
  const subscores = Object.entries(productData?.subscores || {})

  // Find highest and lowest subscores
  const getScoreInsights = () => {
    if (subscores.length === 0) return { highest: null, lowest: null, highestLabel: '', lowestLabel: '' }

    const scored = subscores.map(([name, value]) => ({ name, value }))
    const highest = scored.reduce((max, curr) => curr.value > max.value ? curr : max)
    const lowest = scored.reduce((min, curr) => curr.value < min.value ? curr : min)

    const scoreLabels = {
      nutrition: 'Valori nutrizionali',
      packaging: 'Imballaggio',
	  ingredients: 'Ingredienti',
	  labels: 'Certificazioni',
	  origins: 'Origini Geografiche'
    }

    return {
      highest,
      lowest,
      highestLabel: scoreLabels[highest.name] || highest.name,
      lowestLabel: scoreLabels[lowest.name] || lowest.name
    }
  }

  const scoreInsights = getScoreInsights()

  const handleViewAlternative = () => {
    if (!productData) return
    navigate('/chat', { state: { product: productData } })
  }

  if (!productData) {
    return (
      <main className="min-h-screen p-4 sm:p-8" style={{ backgroundColor: 'var(--color-lime)' }}>
        <div className="mx-auto max-w-md rounded-3xl bg-white p-6 text-center shadow-lg">
          <p className="mb-4 text-[var(--color-primary)]">Nessun risultato da mostrare.</p>
          <button
            onClick={() => navigate('/home')}
            className="rounded-full bg-[var(--color-green)] px-6 py-3 font-semibold text-white transition hover:bg-[var(--color-primary)]"
          >
            Torna alla home
          </button>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen p-4 sm:p-8" style={{ backgroundColor: 'var(--color-lime)' }}>
      <div className="mx-auto max-w-md">
        {/* Header */}
        <div className="mb-12 flex items-center justify-between">
          <h1 className="text-3xl font-bold text-[var(--color-primary)]">
            Prodotto scansionato
          </h1>
          <button
            onClick={() => navigate('/home')}
            className="text-2xl text-[var(--color-primary)]"
          >
            ✕
          </button>
        </div>

        {/* Product Display Circle */}
        <ProductDisplay product={productData} animate={true} />
        
        {/* Explanation */}
        {productData.explanation_short && (
          <p className="rounded-2xl border border-[var(--color-green)] bg-white/80 p-4 text-sm text-[var(--color-primary)]">
            {productData.explanation_short}
          </p>
        )}

        {/* Subscores Insights */}
        {subscores.length > 0 && scoreInsights.highest && scoreInsights.lowest && (
          <div className="space-y-3 mt-6">
            {/* Highest Score */}
            <div className="rounded-2xl border-2 border-[var(--color-green)] bg-white/80 p-4">
              <p className="text-xs font-semibold text-[var(--color-green)] uppercase tracking-wide mb-1">
                Punto di forza
              </p>
              <p className="text-sm text-[var(--color-primary)]">
                <span className="font-bold">{scoreInsights.highestLabel}:</span> Valutazione più alta ({scoreInsights.highest.value}/100)
              </p>
            </div>

            {/* Lowest Score */}
            <div className="rounded-2xl border-2 border-orange-300 bg-orange-50/80 p-4">
              <p className="text-xs font-semibold text-orange-600 uppercase tracking-wide mb-1">
                Area di miglioramento
              </p>
              <p className="text-sm text-orange-700">
                <span className="font-bold">{scoreInsights.lowestLabel}:</span> Valutazione più bassa ({scoreInsights.lowest.value}/100)
              </p>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="mt-8 flex gap-3">
          <button
            onClick={handleViewAlternative}
            className="flex-1 rounded-full bg-[var(--color-green)] px-6 py-3 font-semibold text-white transition hover:bg-[var(--color-primary)]"
          >
            Vedi alternativa
          </button>
          <button
            onClick={() => navigate('/home')}
            className="flex-1 rounded-full border-2 border-white bg-transparent px-6 py-3 font-semibold text-white transition hover:bg-white hover:text-[var(--color-lime)]"
          >
            Annulla
          </button>
        </div>
      </div>
    </main>
  )
}

export default ProductResult
