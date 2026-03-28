import React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ProductDisplay from './ProductDisplay'

const ProductComparison = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const product = location.state?.product
  const betterChoice = location.state?.betterChoice

  return (
    <main className="min-h-screen p-4 sm:p-8" style={{ backgroundColor: 'var(--color-lime)' }}>
      <div className="mx-auto max-w-md">
        <div className="mb-12 flex items-center justify-between">
          <h1 className="text-3xl font-bold text-[var(--color-primary)]">
            Confronto Prodotti
          </h1>
          <button
            onClick={() => navigate('/home')}
            className="text-2xl text-[var(--color-primary)]"
          >
            ✕
          </button>
        </div>

        <div className="rounded-3xl border-2 border-[var(--color-green)] bg-white p-8 text-center">
          <p className="mb-8 text-[var(--color-primary)]">
            Abbiamo trovato una scelta migliore per te!
          </p>
          <ProductDisplay product={betterChoice} animate={true} />
        </div>

        <div className="mt-8 flex gap-3">
          <button
            onClick={() => navigate('/home')}
            className="flex-1 rounded-full bg-[var(--color-green)] px-6 py-3 font-semibold text-white transition hover:bg-[var(--color-primary)]"
          >
            Home
          </button>
        </div>
      </div>
    </main>
  )
}

export default ProductComparison
