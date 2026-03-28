import React from 'react'
import { useNavigate } from 'react-router-dom'
import appleIcon from './assets/icon-food/icon-food-apple.png'
import bananaIcon from './assets/icon-food/icon-food-banana.png'
import eggIcon from './assets/icon-food/icon-food-egg.png'

const HistoryPage = () => {
  const navigate = useNavigate()

  // Mock history data - recent items scanned
  const mockHistory = [
    { id: 1, name: 'mela melinda', score: 8, maxScore: 10, type: 'apple', date: 'Oggi' },
    { id: 2, name: 'mela golden', score: 9, maxScore: 10, type: 'apple', date: 'Oggi' },
    { id: 3, name: 'banana chiquita', score: 7, maxScore: 10, type: 'banana', date: 'Ieri' },
    { id: 4, name: 'uovo biologico', score: 9, maxScore: 10, type: 'egg', date: 'Ieri' },
    { id: 5, name: 'mela rossa', score: 6, maxScore: 10, type: 'apple', date: '2 giorni fa' },
  ]

  // Mock improvement data - based on recent choices
  const mockImprovement = {
    avgScore: 7.8,
    previousAvgScore: 6.5,
    improvement: '+1.3',
    percentageImprovement: '+20%',
    itemsScanned: 5,
  }

  const productIconMap = {
    apple: appleIcon,
    banana: bananaIcon,
    egg: eggIcon,
  }

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="flex items-center justify-between bg-[var(--color-green)] px-6 py-4 text-white shadow-lg">
        <h1 className="text-xl font-semibold">Storico</h1>
        <button
          onClick={() => navigate('/home')}
          className="text-2xl font-bold"
        >
          ✕
        </button>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-md space-y-6 p-4">
        
        {/* Improvement Stats */}
        <div className="rounded-3xl border-2 border-[var(--color-green)] bg-white shadow-lg overflow-hidden">
          <div className="bg-[var(--color-green)] px-6 py-3 text-center text-white font-semibold">
            Miglioramento recente
          </div>
          <div className="bg-[var(--color-cream)] px-6 py-6 text-center space-y-3">
            <div>
              <p className="text-sm font-medium text-[var(--color-green)]">Punteggio medio</p>
              <p className="text-4xl font-bold text-[var(--color-lime)]">{mockImprovement.avgScore}</p>
            </div>
            <div className="border-t border-[var(--color-green)] pt-3">
              <p className="text-sm text-[var(--color-green)]">Miglioramento rispetto a prima:</p>
              <p className="text-2xl font-bold text-[var(--color-lime)]">{mockImprovement.improvement} ({mockImprovement.percentageImprovement})</p>
            </div>
            <p className="text-xs text-[var(--color-green)]">Su {mockImprovement.itemsScanned} articoli scansionati</p>
          </div>
        </div>

        {/* Recent Items */}
        <div>
          <h2 className="mb-4 text-lg font-bold text-[var(--color-primary)]">Articoli recenti</h2>
          <div className="space-y-3">
            {mockHistory.map((item) => (
              <div
                key={item.id}
                className="rounded-2xl border-2 border-[var(--color-green)] bg-white p-4 shadow-md flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <img
                    src={productIconMap[item.type] || appleIcon}
                    alt={item.name}
                    className="h-12 w-12"
                  />
                  <div>
                    <p className="font-semibold text-[var(--color-green)]">{item.name}</p>
                    <p className="text-xs text-gray-500">{item.date}</p>
                  </div>
                </div>
                <p className="text-2xl font-bold text-[var(--color-lime)]">
                  {item.score}/{item.maxScore}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Back Button */}
        <button
          onClick={() => navigate('/home')}
          className="w-full rounded-full bg-[var(--color-green)] px-6 py-3 font-semibold text-white transition hover:bg-[var(--color-primary)]"
        >
          Torna alla home
        </button>
      </div>
    </main>
  )
}

export default HistoryPage
