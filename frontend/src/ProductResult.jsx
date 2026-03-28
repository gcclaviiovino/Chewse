import React, { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ProductDisplay from './ProductDisplay'

const ProductResult = () => {
  const navigate = useNavigate()
  const location = useLocation()

  const productData = location.state?.product

  // Auto-navigate after 2 seconds
  useEffect(() => {
    if (!productData) return

    const timer = setTimeout(() => {
      if (productData.better_choice) {
        navigate('/product-comparison', { state: { product: productData, betterChoice: productData.better_choice } })
      } else {
        navigate('/choice', { state: { product: productData } })
      }
    }, 2000)

    return () => clearTimeout(timer)
  }, [productData, navigate])

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
      </div>
    </main>
  )
}

export default ProductResult
