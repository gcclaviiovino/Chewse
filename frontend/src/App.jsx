import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import profilePic1 from './assets/profile-picture/profile-picture-1.png'
import profilePic2 from './assets/profile-picture/profile-picture-2.png'
import profilePic3 from './assets/profile-picture/profile-picture-3.png'
import appleIcon from './assets/icon-food/icon-food-apple.png'
import historyIcon from './assets/history-icon.png'
import chatIcon from './assets/chat-icon.png'
import CameraCapture from './CameraCapture'
import ProductResult from './ProductResult'
import ChoicePage from './ChoicePage'
import ProductComparison from './ProductComparison'
import SuccessPage from './SuccessPage'
import HistoryPage from './HistoryPage'
import ChatbotPage from './ChatbotPage'
import FriendSearch from './FriendSearch'

function WelcomePage() {
  const navigate = useNavigate()

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <section className="w-full max-w-sm text-center">
        <h1 className="mb-12 text-5xl font-italic text-[var(--color-primary)]" style={{ fontStyle: 'italic' }}>
          Bentornato!
        </h1>

        <div className="space-y-6">
          <div>
            <label className="mb-3 block text-sm font-medium text-[var(--color-green)]">
              Username
            </label>
            <input
              type="text"
              placeholder=""
              className="w-full rounded-full border-2 border-[var(--color-green)] bg-transparent px-6 py-3 outline-none transition focus:border-[var(--color-lime)]"
            />
          </div>

          <div>
            <label className="mb-3 block text-sm font-medium text-[var(--color-green)]">
              Password
            </label>
            <input
              type="password"
              placeholder=""
              className="w-full rounded-full border-2 border-[var(--color-green)] bg-transparent px-6 py-3 outline-none transition focus:border-[var(--color-lime)]"
            />
          </div>

          <button
            onClick={() => navigate('/home')}
            className="w-full rounded-full bg-[var(--color-green)] px-6 py-3 font-semibold text-white transition hover:bg-[var(--color-primary)]"
          >
            Accedi
          </button>
        </div>

        <p className="mt-8 text-sm">
          <span className="text-[var(--color-primary)]">Non hai ancora un account?</span>
          {' '}
          <button
            onClick={() => navigate('/signup')}
            className="font-semibold text-[var(--color-lime)] transition hover:underline"
          >
            Iscriviti!
          </button>
        </p>
      </section>
    </main>
  )
}

function SignUpPage() {
  const navigate = useNavigate()

  const handleSubmit = (event) => {
    event.preventDefault()

    const formData = new FormData(event.currentTarget)
    const name = formData.get('name')
    const surname = formData.get('surname')
    const terms = formData.get('terms')

    if (!terms) {
      alert('Per favore accetta i termini e le condizioni.')
      return
    }

    navigate('/home', { state: { name, surname } })
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <section className="w-full max-w-sm text-center">
        <h1 className="mb-12 text-5xl font-italic text-[var(--color-primary)]" style={{ fontStyle: 'italic' }}>
          Iscriviti
        </h1>

        <form className="space-y-6" onSubmit={handleSubmit}>
          <div>
            <label className="mb-3 block text-sm font-medium text-[var(--color-green)]">
              Nome
            </label>
            <input
              type="text"
              name="name"
              required
              placeholder=""
              className="w-full rounded-full border-2 border-[var(--color-green)] bg-transparent px-6 py-3 outline-none transition focus:border-[var(--color-lime)]"
            />
          </div>

          <div>
            <label className="mb-3 block text-sm font-medium text-[var(--color-green)]">
              Cognome
            </label>
            <input
              type="text"
              name="surname"
              required
              placeholder=""
              className="w-full rounded-full border-2 border-[var(--color-green)] bg-transparent px-6 py-3 outline-none transition focus:border-[var(--color-lime)]"
            />
          </div>

          <div>
            <label className="mb-3 block text-sm font-medium text-[var(--color-green)]">
              Password
            </label>
            <input
              type="password"
              name="password"
              required
              placeholder=""
              className="w-full rounded-full border-2 border-[var(--color-green)] bg-transparent px-6 py-3 outline-none transition focus:border-[var(--color-lime)]"
            />
          </div>

          <div className="flex items-start gap-3">
            <input
              type="checkbox"
              id="terms"
              name="terms"
              className="mt-1 h-4 w-4 cursor-pointer accent-[var(--color-green)]"
            />
            <label htmlFor="terms" className="text-xs text-[var(--color-primary)]">
              Accetto i termini e le condizioni.
            </label>
          </div>

          <button
            type="submit"
            className="w-full rounded-full bg-[var(--color-green)] px-6 py-3 font-semibold text-white transition hover:bg-[var(--color-primary)]"
          >
            Iscriviti
          </button>
        </form>

        <p className="mt-8 text-sm">
          <span className="text-[var(--color-primary)]">Hai già un account?</span>
          {' '}
          <button
            onClick={() => navigate('/')}
            className="font-semibold text-[var(--color-lime)] transition hover:underline"
          >
            Accedi!
          </button>
        </p>
      </section>
    </main>
  )
}

function LoginPage() {
  const navigate = useNavigate()

  const handleSubmit = (event) => {
    event.preventDefault()

    const formData = new FormData(event.currentTarget)
    const email = formData.get('email')

    navigate('/home', { state: { email } })
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-amber-100 via-orange-50 to-lime-100 p-4 sm:p-8">
      <section className="mx-auto max-w-md rounded-2xl border border-orange-200/70 bg-white/90 p-6 shadow-xl shadow-orange-200/50 backdrop-blur sm:p-8">
        <p className="mb-2 text-sm font-semibold uppercase tracking-[0.24em] text-orange-500">
          Social Food
        </p>
        <h1 className="mb-2 text-3xl font-bold text-zinc-800">Welcome back</h1>
        <p className="mb-6 text-sm text-zinc-600">
          Sign in to explore recipes, stories, and nearby food communities.
        </p>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-zinc-700">Email</span>
            <input
              required
              type="email"
              name="email"
              placeholder="you@example.com"
              className="w-full rounded-xl border border-zinc-300 px-4 py-2.5 text-zinc-900 outline-none transition focus:border-orange-400 focus:ring-2 focus:ring-orange-200"
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-sm font-medium text-zinc-700">Password</span>
            <input
              required
              type="password"
              name="password"
              placeholder="********"
              className="w-full rounded-xl border border-zinc-300 px-4 py-2.5 text-zinc-900 outline-none transition focus:border-orange-400 focus:ring-2 focus:ring-orange-200"
            />
          </label>

          <button
            type="submit"
            className="w-full rounded-xl bg-zinc-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-zinc-700"
          >
            Login
          </button>
        </form>
      </section>
    </main>
  )
}

function HomePage() {
  const navigate = useNavigate()
  const location = useLocation()
  const userName = location.state?.name || 'Flavia'
  
  // Mock data
  const mockUser = {
    name: userName,
    points: 1200,
    profilePicture: '👤'
  }

  const mockHighestScoredProduct = {
    name: 'mela melinda',
    score: 8,
    maxScore: 10,
    image: '🍎'
  }

  const mockFriends = [
    { name: 'Carlo', points: 1600, isBest: true },
    { name: 'Tu', points: 1200, isCurrentUser: true },
    { name: 'Lucia', points: 1000 }
  ]

  return (
    <main className="min-h-screen bg-gray-50 p-0">
      <div className="mx-auto max-w-full space-y-6">
        {/* User Profile Header */}
        <div className="flex items-center justify-between bg-[var(--color-green)] px-6 py-4 text-white shadow-lg">
          <div className="flex items-center gap-3">
            <img src={profilePic1} alt="Profile" className="h-10 w-10 rounded-full" />
            <span className="font-semibold">{mockUser.name}</span>
            <button 
              onClick={() => navigate('/history')}
              className="cursor-pointer hover:opacity-80 transition"
              aria-label="View history"
            >
              <img src={historyIcon} alt="History" className="h-6 w-6" />
            </button>
          </div>
          <span className="font-bold">{mockUser.points}pts</span>
        </div>

        {/* Content Container */}
        <div className="mx-auto max-w-md space-y-6 p-4">

        {/* Product of the Week */}
        <div className="overflow-hidden rounded-3xl border-2 border-[var(--color-green)] bg-white shadow-lg">
          <div className="bg-[var(--color-green)] px-6 py-3 text-center text-white font-semibold">
            Prodotto della settimana
          </div>
          <div className="bg-[var(--color-cream)] px-6 py-8 text-center">
            <img src={appleIcon} alt="Product" className="mb-4 mx-auto h-24 w-24" />
            <p className="mb-2 text-sm font-medium text-[var(--color-green)]">
              {mockHighestScoredProduct.name}
            </p>
            <p className="text-3xl font-bold text-[var(--color-lime)]">
              {mockHighestScoredProduct.score}/{mockHighestScoredProduct.maxScore}
            </p>
          </div>
        </div>

        {/* Friends Section */}
        <div>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-bold text-[var(--color-primary)]">
              I tuoi amici
            </h3>
            <button
              onClick={() => navigate('/add-friend')}
              className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-green)] text-lg text-white font-bold transition hover:bg-[var(--color-primary)]"
              aria-label="Add friend"
            >
              +
            </button>
          </div>
          <div className="space-y-3">
            {mockFriends.map((friend, index) => (
              <div
                key={index}
                className="flex items-center justify-between rounded-full border-2 px-4 py-3"
                style={{
                  borderColor: friend.isBest ? 'var(--color-primary)' : 'var(--color-green)',
                  backgroundColor: friend.isBest ? 'var(--color-primary)' : 'white'
                }}
              >
                <div className="flex items-center gap-3">
                  <img
                    src={[profilePic2, profilePic1, profilePic3][index]}
                    alt={friend.name}
                    className="h-8 w-8 rounded-full"
                  />
                  <span
                    className="font-semibold"
                    style={{
                      color: friend.isBest ? 'white' : 'var(--color-primary)'
                    }}
                  >
                    {friend.name}
                    {friend.isBest && ' ⭐'}
                  </span>
                </div>
                <span
                  className="font-bold"
                  style={{
                    color: friend.isBest ? 'white' : 'var(--color-green)'
                  }}
                >
                  {friend.points}pts
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Scan New Product */}
        <div className="flex justify-center py-4">
          <button
            onClick={() => navigate('/camera')}
            className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--color-green)] text-2xl text-white shadow-lg transition hover:bg-[var(--color-primary)]"
          >
            +
          </button>
        </div>
        </div>

        {/* Floating Chat Button */}
        <button
          onClick={() => navigate('/chat')}
          className="fixed bottom-6 right-6 h-16 w-16 rounded-full shadow-lg transition hover:shadow-xl active:scale-95"
          aria-label="Open chat"
        >
          <img src={chatIcon} alt="Chat" className="h-full w-full rounded-full" />
        </button>
      </div>
    </main>
  )
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<WelcomePage />} />
      <Route path="/signup" element={<SignUpPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/home" element={<HomePage />} />
      <Route path="/camera" element={<CameraCapture />} />
      <Route path="/product-result" element={<ProductResult />} />
      <Route path="/choice" element={<ChoicePage />} />
      <Route path="/product-comparison" element={<ProductComparison />} />
      <Route path="/success" element={<SuccessPage />} />
      <Route path="/history" element={<HistoryPage />} />
      <Route path="/chat" element={<ChatbotPage />} />
      <Route path="/add-friend" element={<FriendSearch />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
