import React, { useRef, useCallback, useState } from 'react'
import Webcam from 'react-webcam'
import { useNavigate } from 'react-router-dom'

const CameraCapture = () => {
  const navigate = useNavigate()
  const webcamRef = useRef(null)
  const [isUploading, setIsUploading] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

  const capture = useCallback(async () => {
    if (!webcamRef.current || isUploading) return

    const imageSrc = webcamRef.current.getScreenshot()
    if (!imageSrc) {
      setErrorMessage('Impossibile catturare la foto. Riprova.')
      return
    }

    setIsUploading(true)
    setErrorMessage('')

    try {
      const response = await fetch(`${apiBaseUrl}/api/upload-photo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageSrc, mode: 'fast', locale: 'it-IT' }),
      })

      if (!response.ok) {
        throw new Error('product_invalid')
      }

      const productData = await response.json()

      // Check if product is unknown
      if (productData.name === 'Prodotto sconosciuto') {
        throw new Error('product_invalid')
      }

      navigate('/product-result', { state: { product: productData } })
    } catch (error) {
      console.error('Error sending photo:', error)
      const message = error.message === 'product_invalid' 
        ? 'Prodotto non valido' 
        : 'Errore di connessione al backend.'
      setErrorMessage(message)
    } finally {
      setIsUploading(false)
    }
  }, [webcamRef, navigate, apiBaseUrl, isUploading])

  const videoConstraints = {
  facingMode: { ideal: "environment" }
}

  return (
    <main className="min-h-screen bg-gray-50 p-4 sm:p-8">
      <div className="mx-auto max-w-lg">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-[var(--color-primary)]">Scatta una foto</h1>
          <button
            onClick={() => navigate('/home')}
            className="text-2xl text-[var(--color-green)]"
          >
            ✕
          </button>
        </div>

        {/* Camera View */}
        <div className="mb-6 overflow-hidden rounded-3xl border-4 border-[var(--color-green)] shadow-lg">
          <Webcam
            audio={false}
            ref={webcamRef}
            screenshotFormat="image/jpeg"
            videoConstraints={videoConstraints}
            className="w-full"
          />
        </div>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            onClick={capture}
            disabled={isUploading}
            className="flex-1 rounded-full bg-[var(--color-green)] px-6 py-3 font-semibold text-white transition hover:bg-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-70"
          >
            {isUploading ? 'Invio in corso...' : 'Scatta'}
          </button>
          <button
            onClick={() => navigate('/home')}
            className="flex-1 rounded-full border-2 border-[var(--color-green)] bg-transparent px-6 py-3 font-semibold text-[var(--color-green)] transition hover:bg-gray-100"
          >
            Annulla
          </button>
        </div>

        {errorMessage && (
          <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {errorMessage}
          </p>
        )}
      </div>
    </main>
  )
}

export default CameraCapture
