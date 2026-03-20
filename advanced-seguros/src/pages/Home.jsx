import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Heart, Shield, Users, BadgeDollarSign, Clock, HeadphonesIcon, ChevronDown, Star, Phone } from 'lucide-react'

const operadoras = [
  { nome: 'Unimed', cor: '#16a34a' },
  { nome: 'Amil', cor: '#2563eb' },
  { nome: 'SulAmerica', cor: '#ea580c' },
  { nome: 'Bradesco Saude', cor: '#dc2626' },
  { nome: 'Hapvida', cor: '#0891b2' },
  { nome: 'NotreDame Intermedica', cor: '#7c3aed' },
]

const diferenciais = [
  { icon: HeadphonesIcon, titulo: 'Atendimento Personalizado', desc: 'Consultores especializados que entendem suas necessidades e encontram a melhor solucao.' },
  { icon: BadgeDollarSign, titulo: 'Melhores Precos', desc: 'Negociamos diretamente com as operadoras para garantir as melhores condicoes do mercado.' },
  { icon: Clock, titulo: '+10 Anos de Experiencia', desc: 'Mais de uma decada ajudando familias e empresas a encontrar o plano ideal.' },
  { icon: Users, titulo: 'Suporte Completo', desc: 'Acompanhamento desde a cotacao ate o uso do plano. Estamos sempre ao seu lado.' },
]

const depoimentos = [
  { nome: 'Maria Silva', cargo: 'Empresaria', texto: 'A Advanced Seguros encontrou o plano perfeito para minha empresa. Atendimento incrivel e preco justo!', estrelas: 5 },
  { nome: 'Carlos Oliveira', cargo: 'Medico', texto: 'Profissionais serios e dedicados. Me ajudaram a migrar de plano sem dor de cabeca nenhuma.', estrelas: 5 },
  { nome: 'Ana Costa', cargo: 'Mae de familia', texto: 'Consegui um plano familiar excelente com um valor que cabe no orcamento. Super recomendo!', estrelas: 5 },
]

const faqItems = [
  { pergunta: 'Quanto custa para fazer uma cotacao?', resposta: 'A cotacao e totalmente gratuita e sem compromisso. Entre em contato e receba uma proposta personalizada em ate 24 horas.' },
  { pergunta: 'Voces trabalham com quais operadoras?', resposta: 'Trabalhamos com as principais operadoras do mercado: Unimed, Amil, SulAmerica, Bradesco Saude, Hapvida e NotreDame Intermedica.' },
  { pergunta: 'Posso migrar de plano sem carencia?', resposta: 'Sim! Em muitos casos e possivel aproveitar a carencia ja cumprida no plano anterior. Consulte-nos para avaliar o seu caso.' },
  { pergunta: 'Voces atendem empresas de todos os tamanhos?', resposta: 'Sim, atendemos desde MEI e PME (a partir de 2 vidas) ate grandes empresas. Temos planos especificos para cada perfil.' },
]

function useInView(opts = {}) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    if (rect.top < window.innerHeight && rect.bottom > 0) {
      setVisible(true)
      return
    }
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setVisible(true); obs.unobserve(e.target) }
    }, { threshold: 0.05 })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])
  return [ref, visible]
}

function Reveal({ children, delay = 0, style = {} }) {
  const [ref, visible] = useInView()
  return (
    <div
      ref={ref}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(24px)',
        transition: `opacity 0.6s ease ${delay}ms, transform 0.6s ease ${delay}ms`,
        ...style,
      }}
    >
      {children}
    </div>
  )
}

function FaqItem({ pergunta, resposta }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ borderBottom: '1px solid #e2e8f0' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '20px 0',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
          fontSize: '16px',
          fontWeight: 500,
          color: '#0f172a',
        }}
      >
        <span style={{ paddingRight: '16px' }}>{pergunta}</span>
        <ChevronDown
          style={{
            width: '20px',
            height: '20px',
            color: '#059669',
            flexShrink: 0,
            transform: open ? 'rotate(180deg)' : 'rotate(0)',
            transition: 'transform 0.3s',
          }}
        />
      </button>
      <div style={{
        maxHeight: open ? '200px' : '0',
        overflow: 'hidden',
        transition: 'max-height 0.3s ease',
      }}>
        <p style={{ paddingBottom: '20px', fontSize: '15px', lineHeight: 1.7, color: '#64748b' }}>
          {resposta}
        </p>
      </div>
    </div>
  )
}

export default function Home() {
  return (
    <>
      {/* Hero */}
      <section style={{
        paddingTop: '140px',
        paddingBottom: '80px',
        background: 'linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 30%, #f8fafc 70%, #eff6ff 100%)',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* Decorative circles */}
        <div style={{ position: 'absolute', top: '-100px', right: '-100px', width: '400px', height: '400px', borderRadius: '50%', background: 'rgba(5,150,105,0.05)' }} />
        <div style={{ position: 'absolute', bottom: '-50px', left: '-50px', width: '300px', height: '300px', borderRadius: '50%', background: 'rgba(37,99,235,0.03)' }} />

        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px', position: 'relative', zIndex: 1 }}>
          <div style={{ maxWidth: '720px' }}>
            <div
              className="animate-fade-up"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 16px',
                borderRadius: '100px',
                background: '#d1fae5',
                color: '#047857',
                fontSize: '13px',
                fontWeight: 600,
                marginBottom: '24px',
                letterSpacing: '0.02em',
              }}
            >
              <Heart style={{ width: '14px', height: '14px' }} />
              Corretora de Planos de Saude
            </div>

            <h1
              className="animate-fade-up"
              style={{
                fontSize: 'clamp(32px, 5vw, 56px)',
                fontWeight: 800,
                lineHeight: 1.1,
                color: '#0f172a',
                marginBottom: '20px',
                animationDelay: '0.1s',
              }}
            >
              O plano de saude ideal para voce e sua empresa
            </h1>

            <p
              className="animate-fade-up"
              style={{
                fontSize: '18px',
                lineHeight: 1.7,
                color: '#64748b',
                marginBottom: '36px',
                maxWidth: '560px',
                animationDelay: '0.2s',
              }}
            >
              Comparamos as melhores operadoras do mercado para encontrar o plano perfeito para voce, sua familia ou sua empresa.
            </p>

            <div
              className="animate-fade-up"
              style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', animationDelay: '0.3s' }}
            >
              <Link
                to="/contato"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '14px 28px',
                  background: '#059669',
                  color: '#fff',
                  fontWeight: 600,
                  fontSize: '15px',
                  borderRadius: '10px',
                  textDecoration: 'none',
                  transition: 'background 0.2s, transform 0.2s',
                  boxShadow: '0 4px 14px rgba(5,150,105,0.3)',
                }}
              >
                Solicitar Cotacao Gratis
                <ArrowRight style={{ width: '18px', height: '18px' }} />
              </Link>
              <Link
                to="/planos"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '14px 28px',
                  background: '#fff',
                  color: '#334155',
                  fontWeight: 600,
                  fontSize: '15px',
                  borderRadius: '10px',
                  textDecoration: 'none',
                  border: '1px solid #e2e8f0',
                  transition: 'border-color 0.2s',
                }}
              >
                Ver Planos
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Operadoras */}
      <section style={{ padding: '64px 0', background: '#fff' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px' }}>
          <Reveal>
            <p style={{ textAlign: 'center', fontSize: '13px', fontWeight: 600, color: '#94a3b8', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '32px' }}>
              Operadoras Parceiras
            </p>
          </Reveal>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px' }}>
            {operadoras.map((op, i) => (
              <Reveal key={op.nome} delay={i * 60}>
                <div style={{
                  padding: '20px 16px',
                  borderRadius: '12px',
                  border: '1px solid #f1f5f9',
                  background: '#f8fafc',
                  textAlign: 'center',
                  transition: 'border-color 0.2s, box-shadow 0.2s',
                  cursor: 'default',
                }}>
                  <div style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: op.cor,
                    margin: '0 auto 10px',
                  }} />
                  <span style={{ fontSize: '14px', fontWeight: 600, color: '#334155' }}>{op.nome}</span>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Diferenciais */}
      <section style={{ padding: '80px 0', background: '#f8fafc' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px' }}>
          <Reveal>
            <div style={{ textAlign: 'center', marginBottom: '48px' }}>
              <p style={{ fontSize: '13px', fontWeight: 600, color: '#059669', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '12px' }}>Por que nos escolher</p>
              <h2 style={{ fontSize: 'clamp(24px, 3vw, 36px)', fontWeight: 700, color: '#0f172a' }}>
                Diferenciais que fazem a diferenca
              </h2>
            </div>
          </Reveal>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '24px' }}>
            {diferenciais.map((item, i) => (
              <Reveal key={item.titulo} delay={i * 80}>
                <div style={{
                  padding: '32px 28px',
                  borderRadius: '16px',
                  background: '#fff',
                  border: '1px solid #e2e8f0',
                  transition: 'box-shadow 0.3s, border-color 0.3s',
                  height: '100%',
                }}>
                  <div style={{
                    width: '48px',
                    height: '48px',
                    borderRadius: '12px',
                    background: '#ecfdf5',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: '20px',
                  }}>
                    <item.icon style={{ width: '24px', height: '24px', color: '#059669' }} />
                  </div>
                  <h3 style={{ fontSize: '17px', fontWeight: 600, color: '#0f172a', marginBottom: '8px' }}>{item.titulo}</h3>
                  <p style={{ fontSize: '14px', lineHeight: 1.7, color: '#64748b' }}>{item.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Depoimentos */}
      <section style={{ padding: '80px 0', background: '#fff' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px' }}>
          <Reveal>
            <div style={{ textAlign: 'center', marginBottom: '48px' }}>
              <p style={{ fontSize: '13px', fontWeight: 600, color: '#059669', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '12px' }}>Depoimentos</p>
              <h2 style={{ fontSize: 'clamp(24px, 3vw, 36px)', fontWeight: 700, color: '#0f172a' }}>
                O que nossos clientes dizem
              </h2>
            </div>
          </Reveal>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px' }}>
            {depoimentos.map((dep, i) => (
              <Reveal key={dep.nome} delay={i * 80}>
                <div style={{
                  padding: '32px 28px',
                  borderRadius: '16px',
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                }}>
                  <div style={{ display: 'flex', gap: '2px', marginBottom: '16px' }}>
                    {Array.from({ length: dep.estrelas }).map((_, j) => (
                      <Star key={j} style={{ width: '16px', height: '16px', color: '#f59e0b', fill: '#f59e0b' }} />
                    ))}
                  </div>
                  <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#334155', flex: 1, marginBottom: '20px' }}>
                    "{dep.texto}"
                  </p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', borderTop: '1px solid #e2e8f0', paddingTop: '16px' }}>
                    <div style={{
                      width: '40px',
                      height: '40px',
                      borderRadius: '50%',
                      background: '#d1fae5',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#047857',
                      fontWeight: 700,
                      fontSize: '15px',
                    }}>
                      {dep.nome.charAt(0)}
                    </div>
                    <div>
                      <p style={{ fontSize: '14px', fontWeight: 600, color: '#0f172a' }}>{dep.nome}</p>
                      <p style={{ fontSize: '13px', color: '#94a3b8' }}>{dep.cargo}</p>
                    </div>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section style={{ padding: '80px 0', background: '#f8fafc' }}>
        <div style={{ maxWidth: '720px', margin: '0 auto', padding: '0 24px' }}>
          <Reveal>
            <div style={{ textAlign: 'center', marginBottom: '48px' }}>
              <p style={{ fontSize: '13px', fontWeight: 600, color: '#059669', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '12px' }}>Duvidas frequentes</p>
              <h2 style={{ fontSize: 'clamp(24px, 3vw, 36px)', fontWeight: 700, color: '#0f172a' }}>
                Perguntas e Respostas
              </h2>
            </div>
          </Reveal>
          <Reveal delay={100}>
            <div style={{ background: '#fff', borderRadius: '16px', border: '1px solid #e2e8f0', padding: '8px 28px' }}>
              {faqItems.map((item, i) => (
                <FaqItem key={i} pergunta={item.pergunta} resposta={item.resposta} />
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* CTA */}
      <section style={{
        padding: '80px 0',
        background: 'linear-gradient(135deg, #059669 0%, #047857 100%)',
        color: '#fff',
        textAlign: 'center',
      }}>
        <div style={{ maxWidth: '640px', margin: '0 auto', padding: '0 24px' }}>
          <Reveal>
            <Shield style={{ width: '40px', height: '40px', margin: '0 auto 20px', opacity: 0.8 }} />
            <h2 style={{ fontSize: 'clamp(24px, 3vw, 36px)', fontWeight: 700, marginBottom: '16px' }}>
              Solicite sua cotacao gratuita
            </h2>
            <p style={{ fontSize: '17px', lineHeight: 1.7, opacity: 0.9, marginBottom: '32px' }}>
              Preencha seus dados e receba uma proposta personalizada sem compromisso.
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', justifyContent: 'center' }}>
              <Link
                to="/contato"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '14px 32px',
                  background: '#fff',
                  color: '#047857',
                  fontWeight: 700,
                  fontSize: '15px',
                  borderRadius: '10px',
                  textDecoration: 'none',
                  transition: 'transform 0.2s',
                }}
              >
                Falar com Consultor
                <ArrowRight style={{ width: '18px', height: '18px' }} />
              </Link>
              <a
                href="https://wa.me/5500000000000"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '14px 32px',
                  background: 'rgba(255,255,255,0.15)',
                  color: '#fff',
                  fontWeight: 600,
                  fontSize: '15px',
                  borderRadius: '10px',
                  textDecoration: 'none',
                  border: '1px solid rgba(255,255,255,0.3)',
                }}
              >
                <Phone style={{ width: '16px', height: '16px' }} />
                WhatsApp
              </a>
            </div>
          </Reveal>
        </div>
      </section>
    </>
  )
}
