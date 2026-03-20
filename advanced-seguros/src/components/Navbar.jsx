import { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Menu, X, Shield } from 'lucide-react'

const links = [
  { to: '/', label: 'Inicio' },
  { to: '/planos', label: 'Planos' },
  { to: '/sobre', label: 'Sobre' },
  { to: '/contato', label: 'Contato' },
]

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => setOpen(false), [location])

  return (
    <nav
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 50,
        height: '72px',
        background: scrolled ? 'rgba(255,255,255,0.97)' : 'rgba(255,255,255,0.85)',
        backdropFilter: 'blur(12px)',
        borderBottom: scrolled ? '1px solid #e2e8f0' : '1px solid transparent',
        transition: 'all 0.3s ease',
      }}
    >
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '8px', textDecoration: 'none' }}>
          <Shield style={{ width: '28px', height: '28px', color: '#059669' }} />
          <span style={{ fontSize: '18px', fontWeight: 700, color: '#0f172a' }}>
            Advanced <span style={{ color: '#059669' }}>Seguros</span>
          </span>
        </Link>

        <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }} className="hidden md:flex">
          {links.map(link => (
            <Link
              key={link.to}
              to={link.to}
              style={{
                textDecoration: 'none',
                fontSize: '14px',
                fontWeight: 500,
                color: location.pathname === link.to ? '#059669' : '#475569',
                transition: 'color 0.2s',
              }}
            >
              {link.label}
            </Link>
          ))}
          <Link
            to="/contato"
            style={{
              textDecoration: 'none',
              fontSize: '14px',
              fontWeight: 600,
              color: '#fff',
              background: '#059669',
              padding: '10px 24px',
              borderRadius: '8px',
              transition: 'background 0.2s',
            }}
          >
            Cotacao Gratis
          </Link>
        </div>

        <button
          onClick={() => setOpen(!open)}
          className="md:hidden"
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '8px' }}
        >
          {open
            ? <X style={{ width: '24px', height: '24px', color: '#0f172a' }} />
            : <Menu style={{ width: '24px', height: '24px', color: '#0f172a' }} />
          }
        </button>
      </div>

      {open && (
        <div
          className="md:hidden"
          style={{
            position: 'absolute',
            top: '72px',
            left: 0,
            right: 0,
            background: '#fff',
            borderBottom: '1px solid #e2e8f0',
            padding: '16px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
          }}
        >
          {links.map(link => (
            <Link
              key={link.to}
              to={link.to}
              style={{
                textDecoration: 'none',
                fontSize: '16px',
                fontWeight: 500,
                color: location.pathname === link.to ? '#059669' : '#334155',
                padding: '8px 0',
              }}
            >
              {link.label}
            </Link>
          ))}
          <Link
            to="/contato"
            style={{
              textDecoration: 'none',
              fontSize: '16px',
              fontWeight: 600,
              color: '#fff',
              background: '#059669',
              padding: '12px 24px',
              borderRadius: '8px',
              textAlign: 'center',
              marginTop: '8px',
            }}
          >
            Cotacao Gratis
          </Link>
        </div>
      )}
    </nav>
  )
}
