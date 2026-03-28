import React, { useRef, useCallback } from 'react'
import Webcam from 'react-webcam'
import { useNavigate } from 'react-router-dom'

const CameraCapture = () => {
  const navigate = useNavigate()
  const webcamRef = useRef(null)

  const capture = useCallback(async () => {
    if (!webcamRef.current) return

    // 1. Get the screenshot from the webcam (as a Base64 string)
    const imageSrc = webcamRef.current.getScreenshot()

    // TODO: Uncomment when backend is ready
    // try {
    //   // 2. Send it to your Python backend
    //   const response = await fetch('http://localhost:8000/api/upload-photo', {
    //     method: 'POST',
    //     headers: { 'Content-Type': 'application/json' },
    //     body: JSON.stringify({ image: imageSrc }),
    //   })

    //   if (response.ok) {
    //     const productData = await response.json()
    //     navigate('/product-result', { state: { product: productData } })
    //   } else {
    //     alert('Failed to send photo')
    //   }
    // } catch (error) {
    //   console.error('Error sending photo:', error)
    //   alert('Error sending photo to backend')
    // }

    // TEMPORARY: For testing without backend
    const testProduct = {
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
    navigate('/product-result', { state: { product: testProduct } })
  }, [webcamRef, navigate])

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
            className="w-full"
          />
        </div>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            onClick={capture}
            className="flex-1 rounded-full bg-[var(--color-green)] px-6 py-3 font-semibold text-white transition hover:bg-[var(--color-primary)]"
          >
            Scatta
          </button>
          <button
            onClick={() => navigate('/home')}
            className="flex-1 rounded-full border-2 border-[var(--color-green)] bg-transparent px-6 py-3 font-semibold text-[var(--color-green)] transition hover:bg-gray-100"
          >
            Annulla
          </button>
        </div>
      </div>
    </main>
  )
}

export default CameraCapture
