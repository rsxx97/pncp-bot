import { Link } from 'react-router-dom'
import { Shield, Phone, Mail, MapPin } from 'lucide-react'

export default function Footer() {
  return (
    <footer style={{ background: '#0f172a', color: '#94a3b8', padding: '64px 0 32px' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '40px', marginBottom: '48px' }}>
          {/* Brand */}
          <div>
            <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '8px', textDecoration: 'none', marginBottom: '16px' }}>
              <Shield style={{ width: '24px', height: '24px', color: '#34d399' }} />
              <span style={{ fontSize: '17px', fontWeight: 700, color: '#f1f5f9' }}>
                Advanced <span style={{ color: '#34d399' }}>Seguros</span>
              </span>
            </Link>
            <p style={{ fontSize: '14px', lineHeight: 1.7, color: '#64748b', maxWidth: '280px' }}>
              Sua corretora de planos de saude. Encontramos o plano ideal para voce, sua familia ou sua empresa.
            </p>
          </div>

          {/* Navegacao */}
          <div>
            <h4 style={{ fontSize: '13px', fontWeight: 600, color: '#e2e8f0', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: '16px' }}>Navegacao</h4>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {[
                { to: '/', label: 'Inicio' },
                { to: '/planos', label: 'Planos' },
                { to: '/sobre', label: 'Sobre Nos' },
                { to: '/contato', label: 'Contato' },
              ].map(link => (
                <li key={link.to}>
                  <Link to={link.to} style={{ color: '#64748b', textDecoration: 'none', fontSize: '14px', transition: 'color 0.2s' }}>
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Planos */}
          <div>
            <h4 style={{ fontSize: '13px', fontWeight: 600, color: '#e2e8f0', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: '16px' }}>Planos</h4>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {['Individual', 'Familiar', 'Empresarial', 'PME'].map(tipo => (
                <li key={tipo}>
                  <Link to="/planos" style={{ color: '#64748b', textDecoration: 'none', fontSize: '14px' }}>
                    {tipo}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Contato */}
          <div>
            <h4 style={{ fontSize: '13px', fontWeight: 600, color: '#e2e8f0', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: '16px' }}>Contato</h4>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <li style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px' }}>
                <Phone style={{ width: '14px', height: '14px', color: '#34d399' }} />
                (00) 00000-0000
              </li>
              <li style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px' }}>
                <Mail style={{ width: '14px', height: '14px', color: '#34d399' }} />
                contato@advancedseguros.com.br
              </li>
              <li style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px' }}>
                <MapPin style={{ width: '14px', height: '14px', color: '#34d399' }} />
                Sua cidade, Estado
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom */}
        <div style={{ borderTop: '1px solid #1e293b', paddingTop: '24px', display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: '12px' }}>
          <p style={{ fontSize: '13px', color: '#475569' }}>
            &copy; 2026 Advanced Seguros. Todos os direitos reservados.
          </p>
          <p style={{ fontSize: '13px', color: '#475569' }}>
            SUSEP — Corretora autorizada
          </p>
        </div>
      </div>
    </footer>
  )
}
