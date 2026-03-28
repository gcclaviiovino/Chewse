import React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ProductDisplay from './ProductDisplay'

const ProductResult = () => {
  const navigate = useNavigate()
  const location = useLocation()

  const productData = location.state?.product
  const subscores = Object.entries(productData?.subscores || {})

  const handleViewAlternative = () => {
    if (!productData) return

    if (productData.better_choice) {
      navigate('/product-comparison', { state: { product: productData, betterChoice: productData.better_choice } })
    } else {
      navigate('/choice', { state: { product: productData } })
    }
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
        {productData.explanation_short && (
          <p className="rounded-2xl border border-[var(--color-green)] bg-white/80 p-4 text-sm text-[var(--color-primary)]">
            {productData.explanation_short}
          </p>
        )}

        {/* Action Buttons */}
        <div className="mt-12 flex gap-3">
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
