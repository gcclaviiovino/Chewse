import React from 'react'
import appleIcon from './assets/icon-food/icon-food-apple.png'
import bananaIcon from './assets/icon-food/icon-food-banana.png'
import eggIcon from './assets/icon-food/icon-food-egg.png'

const ProductDisplay = ({ product, animate = true }) => {
  // Product type to icon mapping
  const productIconMap = {
    apple: appleIcon,
    banana: bananaIcon,
    egg: eggIcon,
  }

  const productIcon = productIconMap[product.product_type] || appleIcon

  return (
    <div className="relative mb-12">
      {/* Main Circle */}
      <div 
        className={`aspect-square rounded-full bg-[var(--color-cream)] flex items-center justify-center mx-auto max-w-sm shadow-lg ${animate ? 'animate-pop' : ''}`}
        style={{ boxShadow: '0 0 30px rgba(165, 190, 0, 0.4)' }}
      >
        <div className="text-center">
          <img
            src={productIcon}
            alt={product.name}
            className="h-32 w-32 mb-2 mx-auto"
          />
          <p className="mb-2 text-lg font-bold text-[var(--color-green)]">
            {product.name}
          </p>
          <p className="text-4xl font-bold text-[var(--color-lime)]">
            {product.product_score}/{product.max_score}
          </p>
        </div>
      </div>
    </div>
  )
}

export default ProductDisplay
