import React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

const SuccessPage = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const chosenProduct = location.state?.chosenProduct
  const pointsGathered = location.state?.pointsGathered || 50

  return (
    <main className="min-h-screen p-4 sm:p-8" style={{ backgroundColor: 'var(--color-lime)' }}>
      <div className="mx-auto max-w-md flex flex-col items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="mb-8 text-4xl font-bold text-[var(--color-primary)]">
            Prodotto registrato con successo!
          </h1>
          
          <div className="mb-12 rounded-3xl bg-white p-8">
            <p className="mb-4 text-lg font-bold text-[var(--color-green)]">
              {chosenProduct?.name || 'Prodotto'}
            </p>
            <div className="mb-6 flex items-center justify-center gap-2">
              <span className="text-3xl font-bold text-[var(--color-lime)]">
                +{pointsGathered}
              </span>
              <span className="text-lg font-semibold text-[var(--color-primary)]">
                punti
              </span>
            </div>
          </div>

          <button
            onClick={() => navigate('/home')}
            className="w-full rounded-full bg-[var(--color-green)] px-6 py-3 font-semibold text-white transition hover:bg-[var(--color-primary)]"
          >
            Home
          </button>
        </div>
      </div>
    </main>
  )
}

export default SuccessPage
