export default function Landing({ onStart }) {
  const features = [
    { icon: "🔍", title: "Monitoramento PNCP", desc: "Busca automatica de editais por UF, modalidade e palavras-chave. Filtre por valor, orgao e prazo." },
    { icon: "🤖", title: "Analise com IA", desc: "Extrai postos, atestados e requisitos do PDF. Sugere a melhor empresa do grupo automaticamente." },
    { icon: "📊", title: "Planilha de custos", desc: "Gera planilha de custos com encargos, BDI e margem competitiva. Usa o regime tributario correto." },
    { icon: "🏆", title: "Ranking de empresas", desc: "Cruza atestados, regime tributario e restricoes. Recomenda a empresa mais competitiva para cada edital." },
    { icon: "⚡", title: "Pipeline visual", desc: "Acompanhe cada edital do inicio ao fim: busca, analise, planilha, dossie competitivo." },
    { icon: "🔔", title: "Alertas de prazo", desc: "Veja quais editais vencem em 48h. Nunca perca uma oportunidade por falta de prazo." },
  ];

  const plans = [
    {
      name: "Starter",
      price: "Gratis",
      period: "",
      desc: "Para quem esta comecando",
      features: ["5 editais no pipeline", "Busca no PNCP", "1 empresa cadastrada", "Analise basica"],
      cta: "Comecar gratis",
      highlight: false,
    },
    {
      name: "Pro",
      price: "R$ 297",
      period: "/mes",
      desc: "Para empresas que participam de licitacoes regularmente",
      features: ["Editais ilimitados", "Analise com IA (PDF)", "Planilha de custos", "Ranking de empresas", "3 empresas do grupo", "Alertas por email"],
      cta: "Testar 7 dias gratis",
      highlight: true,
    },
    {
      name: "Enterprise",
      price: "Sob consulta",
      period: "",
      desc: "Para grupos com multiplas empresas e grande volume",
      features: ["Tudo do Pro", "Empresas ilimitadas", "API de integracao", "Dossie competitivo", "Suporte prioritario", "Treinamento da equipe"],
      cta: "Falar com vendas",
      highlight: false,
    },
  ];

  const steps = [
    { num: "1", title: "Cadastre sua empresa", desc: "Informe CNPJ, regime tributario, atestados e UFs de atuacao" },
    { num: "2", title: "Busque oportunidades", desc: "Filtre editais no PNCP por palavra-chave, UF, valor e modalidade" },
    { num: "3", title: "Analise com IA", desc: "O sistema extrai dados do PDF e avalia viabilidade automaticamente" },
    { num: "4", title: "Gere a planilha", desc: "Planilha de custos completa com encargos, BDI e margem competitiva" },
  ];

  return (
    <div style={{ fontFamily: "'DM Sans', sans-serif", minHeight: "100vh", background: "#FAFAFA" }}>
      {/* Header */}
      <div style={{ background: "#1A1A18", color: "#FFF", padding: "14px 24px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 18, fontWeight: 700 }}>Licitacoes AI</span>
        <button onClick={onStart}
          style={{ padding: "7px 18px", background: "#FFF", color: "#1A1A18", border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
          Entrar
        </button>
      </div>

      {/* Hero */}
      <div style={{ textAlign: "center", padding: "70px 24px 50px", maxWidth: 700, margin: "0 auto" }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "#2563EB", textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>Plataforma de licitacoes com IA</div>
        <h1 style={{ fontSize: 38, fontWeight: 800, margin: "0 0 16px", lineHeight: 1.2, color: "#1A1A18" }}>
          Ganhe mais licitacoes com inteligencia artificial
        </h1>
        <p style={{ fontSize: 17, color: "#6B7280", margin: "0 0 28px", lineHeight: 1.6 }}>
          Monitore editais, analise PDFs automaticamente e gere planilhas competitivas de custos. Ideal para empresas de terceirizacao.
        </p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
          <button onClick={onStart}
            style={{ padding: "12px 32px", background: "#1A1A18", color: "#FFF", border: "none", borderRadius: 10, fontSize: 15, fontWeight: 700, cursor: "pointer" }}>
            Comecar gratis
          </button>
          <button onClick={() => document.getElementById("como-funciona")?.scrollIntoView({ behavior: "smooth" })}
            style={{ padding: "12px 32px", background: "#FFF", color: "#1A1A18", border: "1px solid #D1D5DB", borderRadius: 10, fontSize: 15, fontWeight: 600, cursor: "pointer" }}>
            Como funciona
          </button>
        </div>
        <div style={{ fontSize: 13, color: "#9CA3AF", marginTop: 12 }}>Sem cartao de credito. Configure em 5 minutos.</div>
      </div>

      {/* Features */}
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "0 24px 60px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
        {features.map((f, i) => (
          <div key={i} style={{ background: "#FFF", borderRadius: 12, padding: 20, border: "1px solid #E5E7EB" }}>
            <div style={{ fontSize: 28, marginBottom: 10 }}>{f.icon}</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#1A1A18", marginBottom: 6 }}>{f.title}</div>
            <div style={{ fontSize: 13, color: "#6B7280", lineHeight: 1.5 }}>{f.desc}</div>
          </div>
        ))}
      </div>

      {/* Como funciona */}
      <div id="como-funciona" style={{ background: "#FFF", padding: "60px 24px", borderTop: "1px solid #E5E7EB", borderBottom: "1px solid #E5E7EB" }}>
        <div style={{ maxWidth: 800, margin: "0 auto", textAlign: "center" }}>
          <h2 style={{ fontSize: 28, fontWeight: 700, margin: "0 0 8px" }}>Como funciona</h2>
          <p style={{ fontSize: 15, color: "#6B7280", margin: "0 0 40px" }}>4 passos para automatizar suas licitacoes</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 24 }}>
            {steps.map((s, i) => (
              <div key={i} style={{ textAlign: "center" }}>
                <div style={{ width: 40, height: 40, borderRadius: "50%", background: "#1A1A18", color: "#FFF", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 16, fontWeight: 700, marginBottom: 12 }}>{s.num}</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "#1A1A18", marginBottom: 4 }}>{s.title}</div>
                <div style={{ fontSize: 13, color: "#6B7280", lineHeight: 1.4 }}>{s.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Planos */}
      <div style={{ padding: "60px 24px", maxWidth: 960, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <h2 style={{ fontSize: 28, fontWeight: 700, margin: "0 0 8px" }}>Planos</h2>
          <p style={{ fontSize: 15, color: "#6B7280", margin: 0 }}>Escolha o plano ideal para sua empresa</p>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 20 }}>
          {plans.map((p, i) => (
            <div key={i} style={{
              background: "#FFF", borderRadius: 14, padding: 28,
              border: p.highlight ? "2px solid #1A1A18" : "1px solid #E5E7EB",
              position: "relative",
            }}>
              {p.highlight && (
                <div style={{ position: "absolute", top: -12, left: "50%", transform: "translateX(-50%)", background: "#1A1A18", color: "#FFF", padding: "3px 14px", borderRadius: 10, fontSize: 11, fontWeight: 700 }}>
                  MAIS POPULAR
                </div>
              )}
              <div style={{ fontSize: 16, fontWeight: 700, color: "#1A1A18", marginBottom: 4 }}>{p.name}</div>
              <div style={{ fontSize: 13, color: "#6B7280", marginBottom: 16 }}>{p.desc}</div>
              <div style={{ marginBottom: 20 }}>
                <span style={{ fontSize: 32, fontWeight: 800, color: "#1A1A18" }}>{p.price}</span>
                {p.period && <span style={{ fontSize: 14, color: "#9CA3AF" }}>{p.period}</span>}
              </div>
              <ul style={{ listStyle: "none", padding: 0, margin: "0 0 24px" }}>
                {p.features.map((f, j) => (
                  <li key={j} style={{ fontSize: 13, color: "#374151", padding: "4px 0", display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ color: "#16A34A", fontSize: 14 }}>✓</span> {f}
                  </li>
                ))}
              </ul>
              <button onClick={onStart}
                style={{
                  width: "100%", padding: "10px 0", borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: "pointer", border: "none",
                  background: p.highlight ? "#1A1A18" : "#F3F4F6",
                  color: p.highlight ? "#FFF" : "#1A1A18",
                }}>
                {p.cta}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Footer CTA */}
      <div style={{ background: "#1A1A18", padding: "50px 24px", textAlign: "center" }}>
        <h2 style={{ fontSize: 24, fontWeight: 700, color: "#FFF", margin: "0 0 8px" }}>Pronto para automatizar suas licitacoes?</h2>
        <p style={{ fontSize: 14, color: "#9CA3AF", margin: "0 0 20px" }}>Cadastre sua empresa e comece a monitorar editais agora.</p>
        <button onClick={onStart}
          style={{ padding: "12px 32px", background: "#FFF", color: "#1A1A18", border: "none", borderRadius: 8, fontSize: 15, fontWeight: 700, cursor: "pointer" }}>
          Criar conta gratuita
        </button>
      </div>
    </div>
  );
}
