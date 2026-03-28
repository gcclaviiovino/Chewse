import React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ProductDisplay from './ProductDisplay'

const ProductComparison = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const product = location.state?.product
  const betterChoice = location.state?.betterChoice

  const handleChooseProduct = (chosenProduct) => {
    // Mock points for now (will be implemented later)
    const pointsGathered = product.product_score
    navigate('/success', { 
      state: { 
        chosenProduct,
        pointsGathered 
      } 
    })
  }

  return (
    <main className="min-h-screen flex flex-col p-3 sm:p-4" style={{ backgroundColor: 'var(--color-lime)' }}>
      <div className="flex flex-col items-center justify-center flex-1">
        <div className="mb-4 text-center">
          <h1 className="text-2xl font-bold text-[var(--color-primary)]">
            Quale stai prendendo?
          </h1>
        </div>

        {/* Products Comparison - Side by side */}
        <div className="flex gap-8 sm:gap-12 justify-center items-center mb-8">
          {/* Original Product */}
          <button
            onClick={() => handleChooseProduct(product)}
            className="transition transform hover:scale-105 focus:outline-none"
          >
            <ProductDisplay product={product} animate={false} size="small" />
          </button>

          {/* Better Choice Product */}
          <button
            onClick={() => handleChooseProduct(betterChoice)}
            className="transition transform hover:scale-105 focus:outline-none"
          >
            <ProductDisplay product={betterChoice} animate={true} size="small" />
          </button>
        </div>

        <div className="mt-6 flex gap-2 w-full max-w-sm px-4">
          <button
            onClick={() => navigate('/home')}
            className="flex-1 rounded-full bg-white px-6 py-3 font-semibold text-[var(--color-lime)] transition hover:bg-gray-100"
          >
            Annulla
          </button>
        </div>
      </div>
    </main>
  )
}

export default ProductComparison
