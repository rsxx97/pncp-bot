import { useState } from 'react'
import { Phone, Mail, MapPin, Clock, Send, CheckCircle } from 'lucide-react'

const infos = [
  { icon: Phone, titulo: 'Telefone', valor: '(00) 00000-0000' },
  { icon: Mail, titulo: 'Email', valor: 'contato@advancedseguros.com.br' },
  { icon: MapPin, titulo: 'Endereco', valor: 'Sua cidade, Estado' },
  { icon: Clock, titulo: 'Horario', valor: 'Seg a Sex, 9h as 18h' },
]

export default function Contato() {
  const [enviado, setEnviado] = useState(false)
  const [form, setForm] = useState({ nome: '', telefone: '', email: '', tipo: '', mensagem: '' })

  const handleSubmit = (e) => {
    e.preventDefault()
    setEnviado(true)
    setTimeout(() => setEnviado(false), 5000)
    setForm({ nome: '', telefone: '', email: '', tipo: '', mensagem: '' })
  }

  const inputStyle = {
    width: '100%',
    padding: '12px 16px',
    borderRadius: '10px',
    border: '1px solid #e2e8f0',
    fontSize: '15px',
    color: '#0f172a',
    background: '#fff',
    outline: 'none',
    transition: 'border-color 0.2s',
    fontFamily: 'inherit',
  }

  return (
    <>
      {/* Hero */}
      <section style={{
        paddingTop: '130px',
        paddingBottom: '48px',
        background: 'linear-gradient(135deg, #f0fdf4 0%, #f8fafc 100%)',
      }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px', textAlign: 'center' }}>
          <h1 style={{ fontSize: 'clamp(28px, 4vw, 44px)', fontWeight: 800, color: '#0f172a', marginBottom: '12px' }}>
            Fale Conosco
          </h1>
          <p style={{ fontSize: '17px', color: '#64748b', maxWidth: '560px', margin: '0 auto', lineHeight: 1.6 }}>
            Solicite sua cotacao ou tire suas duvidas. Estamos prontos para ajudar.
          </p>
        </div>
      </section>

      {/* Content */}
      <section style={{ padding: '64px 0 80px', background: '#fff' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '48px' }}>
            {/* Info */}
            <div>
              <h2 style={{ fontSize: '24px', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>
                Entre em contato
              </h2>
              <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#64748b', marginBottom: '32px' }}>
                Estamos disponiveis para atender voce da melhor forma. Entre em contato por qualquer um dos nossos canais.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {infos.map(info => (
                  <div key={info.titulo} style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
                    <div style={{
                      width: '44px',
                      height: '44px',
                      borderRadius: '10px',
                      background: '#ecfdf5',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}>
                      <info.icon style={{ width: '20px', height: '20px', color: '#059669' }} />
                    </div>
                    <div>
                      <p style={{ fontSize: '14px', fontWeight: 600, color: '#0f172a', marginBottom: '2px' }}>{info.titulo}</p>
                      <p style={{ fontSize: '14px', color: '#64748b' }}>{info.valor}</p>
                    </div>
                  </div>
                ))}
              </div>

              {/* WhatsApp CTA */}
              <a
                href="https://wa.me/5500000000000"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '10px',
                  marginTop: '32px',
                  padding: '14px 28px',
                  background: '#25d366',
                  color: '#fff',
                  fontWeight: 600,
                  fontSize: '15px',
                  borderRadius: '10px',
                  textDecoration: 'none',
                  transition: 'background 0.2s',
                  boxShadow: '0 4px 12px rgba(37,211,102,0.3)',
                }}
              >
                <Phone style={{ width: '18px', height: '18px' }} />
                Chamar no WhatsApp
              </a>
            </div>

            {/* Form */}
            <div style={{
              padding: '36px 32px',
              borderRadius: '16px',
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
            }}>
              {enviado ? (
                <div style={{ textAlign: 'center', padding: '40px 0' }}>
                  <CheckCircle style={{ width: '48px', height: '48px', color: '#059669', margin: '0 auto 16px' }} />
                  <h3 style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>Mensagem enviada!</h3>
                  <p style={{ fontSize: '15px', color: '#64748b' }}>Retornaremos em ate 24 horas.</p>
                </div>
              ) : (
                <form onSubmit={handleSubmit}>
                  <h3 style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a', marginBottom: '24px' }}>
                    Solicite sua cotacao
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <input
                      type="text"
                      placeholder="Seu nome"
                      required
                      value={form.nome}
                      onChange={e => setForm({ ...form, nome: e.target.value })}
                      style={inputStyle}
                    />
                    <input
                      type="tel"
                      placeholder="Telefone / WhatsApp"
                      required
                      value={form.telefone}
                      onChange={e => setForm({ ...form, telefone: e.target.value })}
                      style={inputStyle}
                    />
                    <input
                      type="email"
                      placeholder="Email"
                      value={form.email}
                      onChange={e => setForm({ ...form, email: e.target.value })}
                      style={inputStyle}
                    />
                    <select
                      value={form.tipo}
                      onChange={e => setForm({ ...form, tipo: e.target.value })}
                      style={{ ...inputStyle, color: form.tipo ? '#0f172a' : '#94a3b8' }}
                    >
                      <option value="">Tipo de plano</option>
                      <option value="Individual">Individual</option>
                      <option value="Familiar">Familiar</option>
                      <option value="Empresarial">Empresarial</option>
                      <option value="PME">PME</option>
                    </select>
                    <textarea
                      placeholder="Mensagem (opcional)"
                      rows={4}
                      value={form.mensagem}
                      onChange={e => setForm({ ...form, mensagem: e.target.value })}
                      style={{ ...inputStyle, resize: 'vertical' }}
                    />
                    <button
                      type="submit"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '8px',
                        padding: '14px',
                        background: '#059669',
                        color: '#fff',
                        fontWeight: 600,
                        fontSize: '15px',
                        borderRadius: '10px',
                        border: 'none',
                        cursor: 'pointer',
                        transition: 'background 0.2s',
                        fontFamily: 'inherit',
                      }}
                    >
                      <Send style={{ width: '16px', height: '16px' }} />
                      Enviar Mensagem
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      </section>
    </>
  )
}
