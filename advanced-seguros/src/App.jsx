import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Footer from './components/Footer'
import WhatsAppButton from './components/WhatsAppButton'
import Home from './pages/Home'
import Planos from './pages/Planos'
import Sobre from './pages/Sobre'
import Contato from './pages/Contato'
import ScrollToTop from './components/ScrollToTop'

function App() {
  return (
    <div style={{ minHeight: '100vh', background: '#ffffff' }}>
      <ScrollToTop />
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/planos" element={<Planos />} />
        <Route path="/sobre" element={<Sobre />} />
        <Route path="/contato" element={<Contato />} />
      </Routes>
      <Footer />
      <WhatsAppButton />
    </div>
  )
}

export default App
