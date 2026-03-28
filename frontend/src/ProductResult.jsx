import React, { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ProductDisplay from './ProductDisplay'

const ProductResult = () => {
  const navigate = useNavigate()
  const location = useLocation()

  // Fake data for testing (will be replaced with backend data)
  const productData = location.state?.product || {
    name: 'mela melinda',
    product_type: 'apple',
    product_score: 8,
    max_score: 10,
    better_choice: {
      name: 'mela golden',
      product_type: 'apple',
      product_score: 9,
      max_score: 10,
    }
  }

  // Auto-navigate after 2 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      if (productData.better_choice) {
        navigate('/product-comparison', { state: { product: productData, betterChoice: productData.better_choice } })
      } else {
        navigate('/choice', { state: { product: productData } })
      }
    }, 2000)

    return () => clearTimeout(timer)
  }, [productData, navigate])

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
      </div>
    </main>
  )
}

export default ProductResult
