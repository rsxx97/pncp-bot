import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Check } from 'lucide-react'

const tipos = ['Todos', 'Individual', 'Familiar', 'Empresarial', 'PME']

const planos = [
  {
    operadora: 'Unimed',
    tipos: ['Individual', 'Familiar', 'Empresarial', 'PME'],
    destaque: 'Maior rede credenciada do Brasil',
    beneficios: ['Ampla rede nacional', 'Cobertura completa', 'Pronto-socorro 24h', 'Telemedicina'],
    cor: '#16a34a',
  },
  {
    operadora: 'Amil',
    tipos: ['Individual', 'Familiar', 'Empresarial'],
    destaque: 'Tecnologia e inovacao em saude',
    beneficios: ['Hospitais proprios', 'App exclusivo', 'Rede premium', 'Atendimento digital'],
    cor: '#2563eb',
  },
  {
    operadora: 'SulAmerica',
    tipos: ['Individual', 'Familiar', 'Empresarial', 'PME'],
    destaque: 'Tradicao e confianca ha mais de 120 anos',
    beneficios: ['Cobertura nacional', 'Reembolso facilitado', 'Rede diferenciada', 'Saude integral'],
    cor: '#ea580c',
  },
  {
    operadora: 'Bradesco Saude',
    tipos: ['Empresarial', 'PME'],
    destaque: 'Solidez e qualidade para empresas',
    beneficios: ['Rede hospitalar premium', 'Gestao de saude', 'Planos flexiveis', 'Abrangencia nacional'],
    cor: '#dc2626',
  },
  {
    operadora: 'Hapvida',
    tipos: ['Individual', 'Familiar', 'PME'],
    destaque: 'Melhor custo-beneficio do mercado',
    beneficios: ['Precos acessiveis', 'Rede propria', 'Clinicas e hospitais', 'Atendimento humanizado'],
    cor: '#0891b2',
  },
  {
    operadora: 'NotreDame Intermedica',
    tipos: ['Individual', 'Familiar', 'Empresarial', 'PME'],
    destaque: 'Rede verticalizada com qualidade',
    beneficios: ['Hospitais proprios', 'Laboratorios integrados', 'Pronto-atendimento', 'Programas preventivos'],
    cor: '#7c3aed',
  },
]

export default function Planos() {
  const [filtro, setFiltro] = useState('Todos')
  const filtrados = filtro === 'Todos' ? planos : planos.filter(p => p.tipos.includes(filtro))

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
            Nossos Planos
          </h1>
          <p style={{ fontSize: '17px', color: '#64748b', maxWidth: '560px', margin: '0 auto', lineHeight: 1.6 }}>
            Trabalhamos com as melhores operadoras do Brasil para oferecer o plano certo para cada necessidade.
          </p>
        </div>
      </section>

      {/* Filtros */}
      <div style={{
        position: 'sticky',
        top: '72px',
        zIndex: 40,
        background: 'rgba(255,255,255,0.95)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid #e2e8f0',
        padding: '16px 0',
      }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px', display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '8px' }}>
          {tipos.map(tipo => (
            <button
              key={tipo}
              onClick={() => setFiltro(tipo)}
              style={{
                padding: '8px 20px',
                borderRadius: '8px',
                fontSize: '14px',
                fontWeight: 500,
                border: filtro === tipo ? 'none' : '1px solid #e2e8f0',
                background: filtro === tipo ? '#059669' : '#fff',
                color: filtro === tipo ? '#fff' : '#475569',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              {tipo}
            </button>
          ))}
        </div>
      </div>

      {/* Grid */}
      <section style={{ padding: '48px 0 80px' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '24px' }}>
            {filtrados.map(plano => (
              <div
                key={plano.operadora}
                style={{
                  padding: '32px 28px',
                  borderRadius: '16px',
                  background: '#fff',
                  border: '1px solid #e2e8f0',
                  display: 'flex',
                  flexDirection: 'column',
                  transition: 'box-shadow 0.3s, border-color 0.3s',
                }}
              >
                <div style={{ marginBottom: '20px' }}>
                  <div style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '4px 12px',
                    borderRadius: '100px',
                    background: `${plano.cor}15`,
                    color: plano.cor,
                    fontSize: '12px',
                    fontWeight: 600,
                    marginBottom: '12px',
                  }}>
                    {plano.tipos.join(' · ')}
                  </div>
                  <h3 style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a', marginBottom: '4px' }}>
                    {plano.operadora}
                  </h3>
                  <p style={{ fontSize: '14px', color: '#64748b' }}>{plano.destaque}</p>
                </div>

                <ul style={{ listStyle: 'none', padding: 0, margin: 0, flex: 1, marginBottom: '24px' }}>
                  {plano.beneficios.map(b => (
                    <li key={b} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '6px 0', fontSize: '14px', color: '#334155' }}>
                      <Check style={{ width: '16px', height: '16px', color: plano.cor, flexShrink: 0 }} />
                      {b}
                    </li>
                  ))}
                </ul>

                <Link
                  to="/contato"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    padding: '12px',
                    borderRadius: '10px',
                    border: `1px solid ${plano.cor}30`,
                    background: `${plano.cor}08`,
                    color: plano.cor,
                    fontWeight: 600,
                    fontSize: '14px',
                    textDecoration: 'none',
                    transition: 'background 0.2s',
                  }}
                >
                  Solicitar Cotacao
                  <ArrowRight style={{ width: '16px', height: '16px' }} />
                </Link>
              </div>
            ))}
          </div>

          {filtrados.length === 0 && (
            <p style={{ textAlign: 'center', color: '#94a3b8', padding: '64px 0', fontSize: '16px' }}>
              Nenhum plano encontrado para este filtro.
            </p>
          )}
        </div>
      </section>
    </>
  )
}
