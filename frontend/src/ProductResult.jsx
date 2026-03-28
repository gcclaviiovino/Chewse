import React, { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ProductDisplay from './ProductDisplay'

const scoreLabels = {
  nutrition: 'Valori nutrizionali',
  packaging: 'Imballaggio',
  ingredients: 'Ingredienti',
  labels: 'Certificazioni',
  origins: 'Origine',
}

const categoryTranslations = {
  breakfasts: 'Colazione',
  snacks: 'Snack',
  biscuits: 'Biscotti',
  cakes: 'Dolci',
  desserts: 'Dessert',
  bread: 'Pane',
  pasta: 'Pasta',
  cereals: 'Cereali',
  fruit: 'Frutta',
  fruits: 'Frutta',
  vegetables: 'Verdura',
  vegetable: 'Verdura',
  legumes: 'Legumi',
  beans: 'Legumi',
  dairy: 'Latticini',
  cheese: 'Formaggi',
  butter: 'Burro',
  fish: 'Pesce',
  seafood: 'Pesce',
  meat: 'Carne',
  beef: 'Manzo',
}

const trustLevelLabels = {
  high: 'Alta',
  medium: 'Media',
  low: 'Bassa',
}

const ProductResult = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const [isTransparencyOpen, setIsTransparencyOpen] = useState(false)

  const productData = location.state?.product
  const subscores = Object.entries(productData?.subscores || {})

  // Find highest and lowest subscores
  const getScoreInsights = () => {
    if (subscores.length === 0) return { highest: null, lowest: null, highestLabel: '', lowestLabel: '' }

    const scored = subscores.map(([name, value]) => ({ name, value }))
    const highest = scored.reduce((max, curr) => curr.value > max.value ? curr : max)
    const lowest = scored.reduce((min, curr) => curr.value < min.value ? curr : min)

    return {
      highest,
      lowest,
      highestLabel: scoreLabels[highest.name] || highest.name,
      lowestLabel: scoreLabels[lowest.name] || lowest.name
    }
  }

  const scoreInsights = getScoreInsights()
  const translatedCategories = (productData?.categories_tags || [])
    .map((tag) => {
      const normalized = String(tag || '')
        .toLowerCase()
        .replace(/^.*:/, '')
        .replaceAll('_', ' ')
        .replaceAll('-', ' ')
        .trim()

      return categoryTranslations[normalized] || normalized.charAt(0).toUpperCase() + normalized.slice(1)
    })
    .filter(Boolean)
    .slice(0, 3)

  const buildPlainLanguageSummary = () => {
    if (!productData) return ''

    const score = Number(productData.product_score || 0)
    let opening = 'Scelta discreta dal punto di vista ambientale.'
    if (score >= 75) {
      opening = 'Buona scelta dal punto di vista ambientale.'
    } else if (score < 45) {
      opening = 'Prodotto con margini di miglioramento dal punto di vista ambientale.'
    }

    const strongestArea = scoreInsights.highest ? scoreLabels[scoreInsights.highest.name] || scoreInsights.highest.name : null
    const weakestArea = scoreInsights.lowest ? scoreLabels[scoreInsights.lowest.name] || scoreInsights.lowest.name : null

    if (strongestArea && weakestArea && strongestArea !== weakestArea) {
      return `${opening} Punto forte: ${strongestArea}. Da migliorare: ${weakestArea}.`
    }

    if (strongestArea) {
      return `${opening} Il punto più positivo riguarda ${strongestArea.toLowerCase()}.`
    }

    return opening
  }

  const plainLanguageSummary = buildPlainLanguageSummary()
  const scoreTransparency = productData?.score_transparency

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
        
        {/* Summary */}
        {plainLanguageSummary && (
          <p className="rounded-2xl border border-[var(--color-green)] bg-white/80 p-4 text-sm text-[var(--color-primary)]">
            {plainLanguageSummary}
          </p>
        )}

        {translatedCategories.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {translatedCategories.map((category) => (
              <span
                key={category}
                className="rounded-full border border-[var(--color-green)] bg-white/80 px-3 py-1 text-xs font-medium text-[var(--color-primary)]"
              >
                {category}
              </span>
            ))}
          </div>
        )}

        {scoreTransparency && (
          <button
            type="button"
            onClick={() => setIsTransparencyOpen((value) => !value)}
            className="mt-6 w-full rounded-3xl border-2 border-[var(--color-green)] bg-white/85 p-4 text-left text-[var(--color-primary)] transition hover:bg-white"
          >
            <div className="flex items-center justify-between gap-4">
              <p className="text-sm font-bold">Come abbiamo calcolato questo punteggio</p>
              <span className="text-xl font-bold text-[var(--color-green)]">
                {isTransparencyOpen ? '−' : '+'}
              </span>
            </div>

            {isTransparencyOpen && (
              <div className="mt-4">
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="rounded-2xl bg-[var(--color-cream)] px-3 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-green)]">Dati certi</p>
                    <p className="mt-1 text-lg font-bold">{scoreTransparency.official_component}/100</p>
                  </div>
                  <div className="rounded-2xl bg-[var(--color-cream)] px-3 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-green)]">Stima AI</p>
                    <p className="mt-1 text-lg font-bold">{scoreTransparency.ai_component}/100</p>
                  </div>
                  <div className="rounded-2xl bg-[var(--color-cream)] px-3 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-green)]">Affidabilità</p>
                    <p className="mt-1 text-lg font-bold">{trustLevelLabels[scoreTransparency.trust_level] || 'Media'}</p>
                  </div>
                </div>

                {scoreTransparency.certainty_summary && (
                  <p className="mt-4 text-sm">{scoreTransparency.certainty_summary}</p>
                )}

                {scoreTransparency.reliable_fields?.length > 0 && (
                  <p className="mt-3 text-sm">
                    <span className="font-semibold">Basato su dati certi:</span>{' '}
                    {scoreTransparency.reliable_fields.join(', ')}.
                  </p>
                )}

                {scoreTransparency.estimated_fields?.length > 0 && (
                  <p className="mt-2 text-sm">
                    <span className="font-semibold">Stimato con AI:</span>{' '}
                    {scoreTransparency.estimated_fields.join(', ')}.
                  </p>
                )}

                {scoreTransparency.missing_fields?.length > 0 && (
                  <p className="mt-2 text-sm">
                    <span className="font-semibold">Dati mancanti:</span>{' '}
                    {scoreTransparency.missing_fields.join(', ')}.
                  </p>
                )}
              </div>
            )}
          </button>
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
