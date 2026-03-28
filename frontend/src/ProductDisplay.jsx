import React from 'react'
import appleIcon from './assets/icon-food/icon-food-apple.png'
import bananaIcon from './assets/icon-food/icon-food-banana.png'
import eggIcon from './assets/icon-food/icon-food-egg.png'

const ProductDisplay = ({ product, animate = true, size = 'large' }) => {
  // Size configurations
  const sizeConfig = {
    large: {
      container: 'max-w-sm',
      icon: 'h-32 w-32',
      nameText: 'text-lg',
      scoreText: 'text-4xl',
      marginBottom: 'mb-12',
    },
    small: {
      container: 'max-w-xs',
      icon: 'h-20 w-20',
      nameText: 'text-md',
      scoreText: 'text-lg',
      marginBottom: 'mb-6',
    },
    tiny: {
      container: 'max-w-96',
      icon: 'h-16 w-16',
      nameText: 'text-xs',
      scoreText: 'text-sm',
      marginBottom: 'mb-3',
    },
  }

  const config = sizeConfig[size] || sizeConfig.large

  // Product type to icon mapping
  const productIconMap = {
    apple: appleIcon,
    banana: bananaIcon,
    egg: eggIcon,
  }

  const productIcon = productIconMap[product.product_type] || appleIcon

  return (
    <div className={`relative ${config.marginBottom}`}>
      {/* Main Circle */}
      <div 
        className={`aspect-square rounded-full bg-[var(--color-cream)] flex items-center justify-center mx-auto ${config.container} shadow-lg ${animate ? 'animate-pop' : ''}`}
        style={{ boxShadow: '0 0 30px rgba(165, 190, 0, 0.4)' }}
      >
        <div className="flex flex-col items-center justify-center p-4">
          <img
            src={productIcon}
            alt={product.name}
            className={`${config.icon} mb-3 mx-auto`}
          />
          <p className={`mb-2 font-bold text-[var(--color-green)] ${config.nameText} text-center px-2`}>
            {product.name}
          </p>
          <p className={`font-bold text-[var(--color-lime)] ${config.scoreText}`}>
            {product.product_score}/{product.max_score}
          </p>
        </div>
      </div>
    </div>
  )
}

export default ProductDisplay
