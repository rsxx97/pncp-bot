import { Shield, Target, Eye, Heart, Award, TrendingUp, Users } from 'lucide-react'

const valores = [
  { icon: Heart, titulo: 'Cuidado', desc: 'Tratamos cada cliente como unico, com atencao e empatia.' },
  { icon: Shield, titulo: 'Confianca', desc: 'Transparencia total em todas as negociacoes e indicacoes.' },
  { icon: Award, titulo: 'Excelencia', desc: 'Buscamos sempre as melhores solucoes do mercado.' },
  { icon: TrendingUp, titulo: 'Inovacao', desc: 'Acompanhamos as tendencias para oferecer o melhor.' },
]

const numeros = [
  { valor: '+10', label: 'Anos de experiencia' },
  { valor: '+1.000', label: 'Clientes atendidos' },
  { valor: '6', label: 'Operadoras parceiras' },
  { valor: '98%', label: 'Satisfacao dos clientes' },
]

export default function Sobre() {
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
            Sobre a Advanced Seguros
          </h1>
          <p style={{ fontSize: '17px', color: '#64748b', maxWidth: '560px', margin: '0 auto', lineHeight: 1.6 }}>
            Mais do que uma corretora, somos parceiros na sua jornada de saude e bem-estar.
          </p>
        </div>
      </section>

      {/* Historia */}
      <section style={{ padding: '80px 0', background: '#fff' }}>
        <div style={{ maxWidth: '800px', margin: '0 auto', padding: '0 24px' }}>
          <p style={{ fontSize: '13px', fontWeight: 600, color: '#059669', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '12px' }}>Nossa Historia</p>
          <h2 style={{ fontSize: 'clamp(24px, 3vw, 32px)', fontWeight: 700, color: '#0f172a', marginBottom: '24px' }}>
            Cuidando da saude de quem importa
          </h2>
          <p style={{ fontSize: '16px', lineHeight: 1.8, color: '#475569', marginBottom: '16px' }}>
            A Advanced Seguros nasceu da vontade de transformar a experiencia de contratar um plano de saude. Sabemos que escolher um plano pode ser confuso e estressante — por isso, simplificamos tudo.
          </p>
          <p style={{ fontSize: '16px', lineHeight: 1.8, color: '#475569' }}>
            Com mais de uma decada de atuacao, ajudamos milhares de pessoas, familias e empresas a encontrar a cobertura ideal, sempre com atendimento humanizado e transparente.
          </p>
        </div>
      </section>

      {/* Missao e Visao */}
      <section style={{ padding: '64px 0', background: '#f8fafc' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px' }}>
            <div style={{ padding: '36px 32px', borderRadius: '16px', background: '#fff', border: '1px solid #e2e8f0' }}>
              <Target style={{ width: '32px', height: '32px', color: '#059669', marginBottom: '16px' }} />
              <h3 style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a', marginBottom: '12px' }}>Missao</h3>
              <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#64748b' }}>
                Facilitar o acesso a planos de saude de qualidade, oferecendo consultoria personalizada e transparente para cada perfil de cliente.
              </p>
            </div>
            <div style={{ padding: '36px 32px', borderRadius: '16px', background: '#fff', border: '1px solid #e2e8f0' }}>
              <Eye style={{ width: '32px', height: '32px', color: '#059669', marginBottom: '16px' }} />
              <h3 style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a', marginBottom: '12px' }}>Visao</h3>
              <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#64748b' }}>
                Ser a corretora de planos de saude mais confiavel e inovadora do mercado, reconhecida pela excelencia no atendimento.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Valores */}
      <section style={{ padding: '80px 0', background: '#fff' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px' }}>
          <div style={{ textAlign: 'center', marginBottom: '48px' }}>
            <p style={{ fontSize: '13px', fontWeight: 600, color: '#059669', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '12px' }}>Nossos Valores</p>
            <h2 style={{ fontSize: 'clamp(24px, 3vw, 32px)', fontWeight: 700, color: '#0f172a' }}>O que nos guia</h2>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '24px' }}>
            {valores.map(v => (
              <div key={v.titulo} style={{ padding: '28px 24px', borderRadius: '16px', background: '#f8fafc', border: '1px solid #e2e8f0', textAlign: 'center' }}>
                <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: '#ecfdf5', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
                  <v.icon style={{ width: '24px', height: '24px', color: '#059669' }} />
                </div>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#0f172a', marginBottom: '8px' }}>{v.titulo}</h3>
                <p style={{ fontSize: '14px', lineHeight: 1.6, color: '#64748b' }}>{v.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Numeros */}
      <section style={{ padding: '64px 0', background: '#059669' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '32px', textAlign: 'center' }}>
            {numeros.map(n => (
              <div key={n.label}>
                <p style={{ fontSize: '36px', fontWeight: 800, color: '#fff', marginBottom: '4px' }}>{n.valor}</p>
                <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.8)' }}>{n.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  )
}
