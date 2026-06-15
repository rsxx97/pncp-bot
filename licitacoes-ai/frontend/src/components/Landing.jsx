import { useState, useEffect, useRef } from "react";

/* ─── Ícones SVG ─────────────────────────────────────────────────────── */
const Icon = ({ d, size = 22, stroke = "#10B981", sw = 1.8 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">{d}</svg>
);
const IconSearch = (c, s) => <Icon stroke={c} size={s} d={<><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></>} />;
const IconAI = (c) => <Icon stroke={c} d={<><path d="M12 3v3M12 18v3M3 12h3M18 12h3" /><rect x="7" y="7" width="10" height="10" rx="2" /><path d="M10 10h4v4h-4z" /></>} />;
const IconSheet = (c) => <Icon stroke={c} d={<><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M3 15h18M9 3v18M15 3v18" /></>} />;
const IconTrophy = (c) => <Icon stroke={c} d={<><path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4Z" /><path d="M17 5h3v2a3 3 0 0 1-3 3M7 5H4v2a3 3 0 0 0 3 3" /></>} />;
const IconFlow = (c) => <Icon stroke={c} d={<><rect x="3" y="4" width="5" height="16" rx="1" /><rect x="10" y="4" width="5" height="10" rx="1" /><rect x="17" y="4" width="4" height="13" rx="1" /></>} />;
const IconBell = (c) => <Icon stroke={c} d={<><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></>} />;
const IconCheck = (c = "#10B981", s = 16) => <Icon size={s} stroke={c} d={<path d="M20 6 9 17l-5-5" />} />;
const IconArrow = (c = "#94A3B8") => <Icon size={16} stroke={c} d={<><path d="M5 12h14M13 6l6 6-6 6" /></>} />;
const IconChevron = (c = "#94A3B8") => <Icon size={18} stroke={c} d={<path d="m6 9 6 6 6-6" />} />;

/* ─── Paleta ──────────────────────────────────────────────────────────── */
const C = {
  ink: "#0B1220", inkSoft: "#111A2B", line: "#1E293B",
  green: "#10B981", greenSoft: "#34D399", blue: "#60A5FA",
  txt: "#E5E9F0", mut: "#94A3B8", light: "#F8FAFC",
};

const FEATURES = [
  { Ic: IconSearch, t: "Monitoramento PNCP", d: "Varredura automática de editais por UF, modalidade e palavra-chave. Filtre por valor, órgão e prazo." },
  { Ic: IconAI, t: "Análise com IA", d: "Extrai postos, atestados e requisitos direto do PDF. Sugere a melhor empresa do grupo para cada edital." },
  { Ic: IconSheet, t: "Planilha de custos", d: "Gera a planilha com encargos, BDI e margem competitiva — já no regime tributário certo." },
  { Ic: IconTrophy, t: "Ranking competitivo", d: "Cruza atestados, regime e restrições e recomenda a empresa mais forte para vencer." },
  { Ic: IconFlow, t: "Pipeline visual", d: "Acompanhe cada edital do início ao fim: busca, análise, planilha e dossiê do concorrente." },
  { Ic: IconBell, t: "Radar ao vivo", d: "Acompanhe a sessão de disputa em tempo real: chat do pregoeiro, lances e fase, sem perder prazo." },
];
const STEPS = [
  { n: "1", t: "Cadastre sua empresa", d: "CNPJ, regime tributário, atestados e UFs de atuação." },
  { n: "2", t: "Busque oportunidades", d: "Filtre editais no PNCP por palavra-chave, UF, valor e modalidade." },
  { n: "3", t: "Analise com IA", d: "O sistema lê o PDF e avalia a viabilidade automaticamente." },
  { n: "4", t: "Gere a planilha", d: "Custos completos com encargos, BDI e margem competitiva." },
];
const PLANS = [
  { name: "Starter", price: "Grátis", period: "", desc: "Para quem está começando",
    features: ["5 editais no pipeline", "Busca no PNCP", "1 empresa cadastrada", "Análise básica"], cta: "Começar grátis", hi: false },
  { name: "Pro", price: "R$ 297", period: "/mês", desc: "Para quem participa toda semana",
    features: ["Editais ilimitados", "Análise com IA (PDF)", "Planilha de custos", "Ranking de empresas", "Radar ao vivo", "Alertas por e-mail"], cta: "Testar 7 dias grátis", hi: true },
  { name: "Enterprise", price: "Sob consulta", period: "", desc: "Para grupos com várias empresas",
    features: ["Tudo do Pro", "Empresas ilimitadas", "API de integração", "Dossiê competitivo", "Suporte prioritário"], cta: "Falar com vendas", hi: false },
];
const SETORES = ["Limpeza & conservação", "Vigilância", "Obras & reforma", "Apoio administrativo", "Resíduos", "Locação de veículos", "TI"];
const BUSCAS_RAPIDAS = ["limpeza e conservação", "vigilância armada", "obras e reforma", "apoio administrativo", "locação de veículos"];
const SAMPLE = [
  { obj: "Limpeza e conservação predial", org: "Tribunal de Justiça do RJ", uf: "RJ", val: "R$ 4,2M", prazo: "8 dias", tags: ["limpeza", "conservação", "predial"] },
  { obj: "Vigilância armada e desarmada", org: "Universidade Federal — RJ", uf: "RJ", val: "R$ 6,1M", prazo: "3 dias", tags: ["vigilância", "armada", "segurança"] },
  { obj: "Apoio administrativo · 45 postos", org: "PRF-RJ", uf: "RJ", val: "R$ 7,9M", prazo: "5 dias", tags: ["apoio", "administrativo", "postos"] },
  { obj: "Reforma de unidade escolar", org: "Pref. de Belford Roxo", uf: "RJ", val: "R$ 12,4M", prazo: "12 dias", tags: ["obras", "reforma", "escola"] },
  { obj: "Locação de veículos com motorista", org: "CRESS-RJ", uf: "RJ", val: "R$ 88 mil", prazo: "6 dias", tags: ["locação", "veículos", "transporte"] },
  { obj: "Coleta de resíduos de serviços de saúde", org: "Secretaria Estadual de Saúde", uf: "RJ", val: "R$ 3,3M", prazo: "9 dias", tags: ["resíduos", "coleta", "saúde"] },
];
const FAQ = [
  { q: "De onde vêm os editais?", a: "Direto do PNCP (Portal Nacional de Contratações Públicas), a fonte oficial do governo. Cobrimos as 27 UFs e todas as modalidades." },
  { q: "Preciso de cartão de crédito para testar?", a: "Não. O plano Starter é gratuito e você configura sua empresa em poucos minutos. O Pro tem 7 dias de teste." },
  { q: "O Radar ao vivo funciona em qualquer pregão?", a: "Acompanha sessões de disputa do ComprasNet em tempo real — chat do pregoeiro, lances e mudança de fase — para você não perder o momento certo." },
  { q: "A planilha de custos serve para terceirização?", a: "Sim. Gera custos com encargos, BDI e margem no regime tributário correto, seguindo o modelo de mão de obra (IN 05/2017) e de obras." },
];
const CHAT = [
  "“Srs. licitantes, item 3 em negociação. Aguardo contraproposta.”",
  "“Boa tarde a todos. Sessão reiniciada às 14h05.”",
  "“Convocando o arrematante para envio da documentação.”",
  "“Item 5 aceito e habilitado. Seguimos para o próximo.”",
];
const COMPARA = {
  sem: ["Procurar editais portal por portal, todo dia", "Ler PDFs de 80 páginas na mão", "Montar a planilha de custos do zero no Excel", "Descobrir o resultado só depois da sessão"],
  com: ["Editais do Brasil inteiro num feed só", "IA extrai postos, atestados e requisitos do PDF", "Planilha pronta com encargos, BDI e margem", "Radar ao vivo: chat, lances e fase em tempo real"],
};
const NAV = [["Recursos", "recursos"], ["Como funciona", "como-funciona"], ["Planos", "planos"], ["Dúvidas", "faq"]];

/* ─── Count-up ───────────────────────────────────────────────────────── */
function CountUp({ to, decimals = 0, prefix = "", suffix = "", start }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!start) return;
    let raf, t0;
    const dur = 1300;
    const tick = (t) => {
      if (t0 == null) t0 = t;
      const p = Math.min(1, (t - t0) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setV(to * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [start, to]);
  return <>{prefix}{v.toFixed(decimals).replace(".", ",")}{suffix}</>;
}

export default function Landing({ onStart }) {
  const [query, setQuery] = useState("");
  const [focused, setFocused] = useState(false);
  const [statsOn, setStatsOn] = useState(false);
  const [faqOpen, setFaqOpen] = useState(0);
  const [lance, setLance] = useState(7.42);
  const [chatIdx, setChatIdx] = useState(0);
  const [scrolled, setScrolled] = useState(false);
  const statsRef = useRef(null);

  // Reveal ao rolar
  useEffect(() => {
    const els = document.querySelectorAll("[data-reveal]");
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { threshold: 0.12 });
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  // Dispara count-up quando a faixa entra na tela
  useEffect(() => {
    if (!statsRef.current) return;
    const io = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) { setStatsOn(true); io.disconnect(); }
    }, { threshold: 0.4 });
    io.observe(statsRef.current);
    return () => io.disconnect();
  }, []);

  // Preview "ao vivo": lance caindo + chat rotativo + CTA flutuante
  useEffect(() => {
    const a = setInterval(() => setLance((p) => { const n = p - (0.01 + Math.random() * 0.045); return n < 6.85 ? 7.6 : n; }), 2200);
    const b = setInterval(() => setChatIdx((i) => (i + 1) % CHAT.length), 3800);
    const onScroll = () => setScrolled(window.scrollY > 680);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => { clearInterval(a); clearInterval(b); window.removeEventListener("scroll", onScroll); };
  }, []);

  const irParaBusca = () => {
    if (query.trim()) { try { localStorage.setItem("busca_inicial", query.trim()); } catch {} }
    onStart?.();
  };

  const q = query.trim().toLowerCase();
  const matches = q
    ? SAMPLE.filter((s) => (s.obj + " " + s.tags.join(" ")).toLowerCase().includes(q)).slice(0, 4)
    : [];
  const showResults = focused && q.length >= 2 && matches.length > 0;

  return (
    <div style={{ fontFamily: "'DM Sans', system-ui, sans-serif", background: "#FFF", color: C.ink }}>
      <style>{`
        html{ scroll-behavior:smooth }
        @keyframes lpFade { from {opacity:0; transform:translateY(14px)} to {opacity:1; transform:none} }
        @keyframes lpFadeIn { from {opacity:0} to {opacity:1} }
        @keyframes lpPulse { 0%,100%{opacity:1} 50%{opacity:.35} }
        @keyframes lpFloat { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-8px)} }
        @keyframes lpDrift { 0%,100%{transform:translate(0,0)} 50%{transform:translate(30px,-20px)} }
        @keyframes lpUp { from {opacity:0; transform:translateY(20px)} to {opacity:1; transform:none} }
        .lp-fade { animation: lpFade .7s ease both }
        [data-reveal]{ opacity:0; transform:translateY(20px); transition:opacity .65s ease, transform .65s ease }
        [data-reveal].in{ opacity:1; transform:none }
        .lp-card{ transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease }
        .lp-card:hover{ transform:translateY(-5px); box-shadow:0 20px 44px rgba(2,6,23,.12); border-color:#CBD5E1 }
        .lp-card:hover .lp-feat-ic{ transform:scale(1.12) rotate(-4deg) }
        .lp-feat-ic{ transition:transform .2s ease }
        .lp-btn{ transition:transform .15s ease, box-shadow .2s ease, filter .2s ease; position:relative }
        .lp-btn:hover{ transform:translateY(-2px); filter:brightness(1.05) }
        .lp-btn:active{ transform:translateY(0) }
        .lp-chip{ transition:all .15s ease }
        .lp-chip:hover{ background:#10B981; color:#06281E; border-color:#10B981 }
        .lp-res{ transition:background .12s ease }
        .lp-res:hover{ background:#F1F5F9 }
        .lp-pulse{ animation: lpPulse 1.6s ease-in-out infinite }
        .lp-float{ animation: lpFloat 6s ease-in-out infinite }
        .lp-faq{ transition:background .15s ease }
        .lp-glow{ background:linear-gradient(135deg,#10B981,#34D399); box-shadow:0 16px 40px rgba(16,185,129,.3) }
        .lp-navlink{ color:#94A3B8; font-size:13.5px; font-weight:600; text-decoration:none; transition:color .15s ease }
        .lp-navlink:hover{ color:#FFF }
        .lp-orb{ position:absolute; border-radius:50%; filter:blur(70px); pointer-events:none }
        .lp-chatmsg{ animation: lpFadeIn .5s ease }
        .lp-fab{ animation: lpUp .35s ease both }
        @media (max-width: 760px){
          .lp-preview-grid{ grid-template-columns:1fr !important }
          .lp-navlinks{ display:none !important }
          .lp-compara{ grid-template-columns:1fr !important }
        }
      `}</style>

      {/* CTA flutuante */}
      {scrolled && (
        <button className="lp-btn lp-glow lp-fab" onClick={onStart} style={{ position: "fixed", right: 22, bottom: 22, zIndex: 60, padding: "13px 22px", color: "#06281E", border: "none", borderRadius: 999, fontSize: 14, fontWeight: 800, cursor: "pointer" }}>
            Criar conta grátis →
        </button>
      )}

      {/* ── Header ── */}
      <header style={{ position: "sticky", top: 0, zIndex: 40, background: "rgba(11,18,32,.82)", backdropFilter: "blur(12px)", borderBottom: `1px solid ${C.line}` }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "13px 24px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div className="lp-glow" style={{ width: 30, height: 30, borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "none" }}>{IconSearch("#06281E", 18)}</div>
            <span style={{ fontSize: 17, fontWeight: 800, color: "#FFF", letterSpacing: -0.3 }}>Licitações<span style={{ color: C.greenSoft }}>AI</span></span>
          </div>
          <div className="lp-navlinks" style={{ display: "flex", gap: 26, alignItems: "center" }}>
            {NAV.map(([t, id]) => <a key={id} href={`#${id}`} className="lp-navlink">{t}</a>)}
          </div>
          <nav style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button className="lp-btn" onClick={onStart} style={{ padding: "8px 16px", background: "transparent", color: C.txt, border: `1px solid ${C.line}`, borderRadius: 9, fontSize: 13.5, fontWeight: 600, cursor: "pointer" }}>Entrar</button>
            <button className="lp-btn lp-glow" onClick={onStart} style={{ padding: "8px 18px", color: "#06281E", border: "none", borderRadius: 9, fontSize: 13.5, fontWeight: 700, cursor: "pointer", boxShadow: "none" }}>Criar conta</button>
          </nav>
        </div>
      </header>

      {/* ── Hero ── */}
      <section style={{ position: "relative", background: `radial-gradient(1100px 520px at 50% -8%, rgba(16,185,129,.2), transparent 60%), radial-gradient(900px 500px at 85% 10%, rgba(96,165,250,.14), transparent 55%), linear-gradient(180deg, ${C.ink}, ${C.inkSoft})`, padding: "70px 24px 96px", overflow: "hidden" }}>
        <div className="lp-orb" style={{ width: 320, height: 320, background: "rgba(16,185,129,.16)", top: -60, left: -40, animation: "lpDrift 14s ease-in-out infinite" }} />
        <div className="lp-orb" style={{ width: 280, height: 280, background: "rgba(96,165,250,.14)", bottom: 40, right: -30, animation: "lpDrift 18s ease-in-out infinite reverse" }} />
        <div className="lp-fade" style={{ maxWidth: 780, margin: "0 auto", textAlign: "center", position: "relative", zIndex: 5 }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "5px 14px", borderRadius: 999, background: "rgba(16,185,129,.12)", border: "1px solid rgba(16,185,129,.3)", color: C.greenSoft, fontSize: 12.5, fontWeight: 700, marginBottom: 22 }}>
            <span className="lp-pulse" style={{ width: 7, height: 7, borderRadius: "50%", background: C.green, boxShadow: "0 0 0 4px rgba(16,185,129,.25)" }} />
            Monitoramento de licitações com IA
          </div>
          <h1 style={{ fontSize: "clamp(33px, 5.2vw, 52px)", fontWeight: 800, lineHeight: 1.07, letterSpacing: -1.2, margin: "0 0 18px", color: "#FFF" }}>
            Encontre a licitação certa<br /><span style={{ background: `linear-gradient(120deg, ${C.greenSoft}, ${C.blue})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>antes dos concorrentes</span>
          </h1>
          <p style={{ fontSize: 17.5, color: C.mut, lineHeight: 1.6, margin: "0 auto 30px", maxWidth: 560 }}>
            Monitore o PNCP, analise editais com IA e gere planilhas de custos competitivas. Feito para empresas de terceirização, obras e serviços.
          </p>

          {/* Busca + resultados ao vivo */}
          <div style={{ position: "relative", maxWidth: 640, margin: "0 auto", zIndex: 10 }}>
            <div style={{ background: "#FFF", borderRadius: showResults ? "16px 16px 0 0" : 16, padding: 8, display: "flex", gap: 8, alignItems: "center", boxShadow: "0 24px 60px rgba(2,6,23,.5)", flexWrap: "wrap" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 220, padding: "0 12px" }}>
                {IconSearch("#94A3B8", 20)}
                <input value={query} onChange={(e) => setQuery(e.target.value)}
                  onFocus={() => setFocused(true)} onBlur={() => setTimeout(() => setFocused(false), 150)}
                  onKeyDown={(e) => e.key === "Enter" && irParaBusca()}
                  placeholder="Ex: limpeza e conservação predial no RJ"
                  style={{ flex: 1, border: "none", outline: "none", fontSize: 15.5, padding: "14px 0", color: C.ink, fontFamily: "inherit", background: "transparent" }} />
              </div>
              <button className="lp-btn lp-glow" onClick={irParaBusca} style={{ padding: "13px 26px", color: "#06281E", border: "none", borderRadius: 11, fontSize: 15, fontWeight: 800, cursor: "pointer", whiteSpace: "nowrap", boxShadow: "none" }}>Buscar editais</button>
            </div>

            {showResults && (
              <div style={{ position: "absolute", left: 0, right: 0, top: "100%", background: "#FFF", borderRadius: "0 0 16px 16px", boxShadow: "0 30px 60px rgba(2,6,23,.45)", overflow: "hidden", textAlign: "left", borderTop: "1px solid #EEF2F7" }}>
                {matches.map((m, i) => (
                  <div key={i} className="lp-res" onMouseDown={irParaBusca} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", cursor: "pointer", borderTop: i ? "1px solid #F1F5F9" : "none" }}>
                    <div style={{ width: 34, height: 34, borderRadius: 9, background: "rgba(16,185,129,.1)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>{IconSearch("#10B981", 16)}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: C.ink, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{m.obj}</div>
                      <div style={{ fontSize: 12, color: "#94A3B8", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{m.org} · {m.uf}</div>
                    </div>
                    <div style={{ textAlign: "right", flexShrink: 0 }}>
                      <div style={{ fontSize: 13.5, fontWeight: 800, color: "#0F172A" }}>{m.val}</div>
                      <div style={{ fontSize: 11, color: "#EF7C3B", fontWeight: 600 }}>fecha em {m.prazo}</div>
                    </div>
                    {IconArrow("#CBD5E1")}
                  </div>
                ))}
                <div onMouseDown={irParaBusca} style={{ padding: "10px 16px", background: "#F8FAFC", fontSize: 12.5, fontWeight: 700, color: "#10B981", cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
                  Ver todos os resultados no app {IconArrow("#10B981")}
                </div>
              </div>
            )}
          </div>

          {!showResults && (
            <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap", marginTop: 16 }}>
              {BUSCAS_RAPIDAS.map((b) => (
                <button key={b} className="lp-chip" onClick={() => setQuery(b)} style={{ padding: "6px 13px", borderRadius: 999, background: "rgba(255,255,255,.05)", border: `1px solid ${C.line}`, color: C.mut, fontSize: 12.5, fontWeight: 600, cursor: "pointer" }}>{b}</button>
              ))}
            </div>
          )}

          <div style={{ display: "flex", gap: 22, justifyContent: "center", flexWrap: "wrap", marginTop: 28, color: C.mut, fontSize: 13 }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>{IconCheck(C.greenSoft)} Sem cartão de crédito</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>{IconCheck(C.greenSoft)} Configure em 5 minutos</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>{IconCheck(C.greenSoft)} Dados oficiais do PNCP</span>
          </div>
        </div>

        {/* Preview do app (Radar ao vivo) */}
        <div data-reveal style={{ maxWidth: 880, margin: "54px auto 0", position: "relative", zIndex: 5 }}>
          <div className="lp-float" style={{ background: "linear-gradient(180deg,#0E1726,#0B1220)", border: `1px solid ${C.line}`, borderRadius: 16, boxShadow: "0 40px 90px rgba(2,6,23,.6)", overflow: "hidden" }}>
            {/* chrome */}
            <div style={{ display: "flex", alignItems: "center", gap: 7, padding: "11px 14px", borderBottom: `1px solid ${C.line}`, background: "rgba(255,255,255,.02)" }}>
              <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#FF5F57" }} />
              <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#FEBC2E" }} />
              <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#28C840" }} />
              <span style={{ marginLeft: 12, fontSize: 12, color: C.mut, fontWeight: 600 }}>Radar — Ao vivo</span>
              <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11.5, color: C.greenSoft, fontWeight: 700 }}>
                <span className="lp-pulse" style={{ width: 7, height: 7, borderRadius: "50%", background: C.green }} /> AO VIVO
              </span>
            </div>
            <div className="lp-preview-grid" style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: 0 }}>
              {/* coluna pregões */}
              <div style={{ padding: 16, borderRight: `1px solid ${C.line}` }}>
                {[
                  { n: "PE 90001/2026", o: "PRF-RJ · Apoio administrativo", st: "Em disputa", c: C.green },
                  { n: "PE 90006/2026", o: "Receita Federal · Apoio adm", st: "Habilitação", c: C.blue },
                  { n: "PE 90020/2026", o: "HNMD Marinha · 81 postos", st: "Agendado", c: "#94A3B8" },
                ].map((p, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 11, padding: "11px 12px", borderRadius: 11, background: i === 0 ? "rgba(16,185,129,.08)" : "transparent", border: i === 0 ? "1px solid rgba(16,185,129,.25)" : "1px solid transparent", marginBottom: 7 }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: p.c }} className={i === 0 ? "lp-pulse" : ""} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: "#FFF" }}>{p.n}</div>
                      <div style={{ fontSize: 11.5, color: C.mut, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p.o}</div>
                    </div>
                    <span style={{ fontSize: 10.5, fontWeight: 700, color: p.c, background: "rgba(255,255,255,.04)", padding: "3px 8px", borderRadius: 6, whiteSpace: "nowrap" }}>{p.st}</span>
                  </div>
                ))}
              </div>
              {/* coluna chat/lance */}
              <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ fontSize: 11, color: C.mut, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.6 }}>Chat do pregoeiro</div>
                <div key={chatIdx} className="lp-chatmsg" style={{ background: "rgba(96,165,250,.1)", border: "1px solid rgba(96,165,250,.2)", borderRadius: 10, padding: "9px 11px", fontSize: 12.5, color: "#DBEAFE", lineHeight: 1.45, minHeight: 54 }}>
                  {CHAT[chatIdx]}
                </div>
                <div style={{ marginTop: 4, display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(16,185,129,.08)", border: "1px solid rgba(16,185,129,.22)", borderRadius: 10, padding: "10px 12px" }}>
                  <span style={{ fontSize: 11.5, color: C.mut, fontWeight: 600 }}>Menor lance</span>
                  <span style={{ fontSize: 16, fontWeight: 800, color: C.greenSoft }}>R$ {lance.toFixed(2).replace(".", ",")}M ▼</span>
                </div>
                <button className="lp-btn lp-glow" onClick={onStart} style={{ marginTop: 2, padding: "9px 0", border: "none", borderRadius: 10, color: "#06281E", fontSize: 12.5, fontWeight: 800, cursor: "pointer", boxShadow: "none" }}>Abrir no Radar</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Faixa de números ── */}
      <div ref={statsRef} style={{ background: C.inkSoft, borderTop: `1px solid ${C.line}`, borderBottom: `1px solid ${C.line}` }}>
        <div style={{ maxWidth: 920, margin: "0 auto", padding: "30px 24px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px,1fr))", gap: 20, textAlign: "center" }}>
          {[
            { node: <CountUp to={700} prefix="+" start={statsOn} />, l: "editais monitorados" },
            { node: <CountUp to={27} start={statsOn} />, l: "UFs cobertas" },
            { node: <CountUp to={1.4} decimals={1} prefix="R$ " suffix=" bi" start={statsOn} />, l: "em oportunidades" },
            { node: "Tempo real", l: "radar de disputa" },
          ].map((s, i) => (
            <div key={i}>
              <div style={{ fontSize: 28, fontWeight: 800, color: "#FFF", letterSpacing: -0.6 }}>{s.node}</div>
              <div style={{ fontSize: 13, color: C.mut, marginTop: 2 }}>{s.l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Setores ── */}
      <div style={{ maxWidth: 1000, margin: "0 auto", padding: "34px 24px 8px", textAlign: "center" }}>
        <div data-reveal style={{ fontSize: 12.5, color: "#94A3B8", fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, marginBottom: 16 }}>Feito para os setores que mais licitam</div>
        <div data-reveal style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
          {SETORES.map((s) => (
            <span key={s} style={{ padding: "7px 15px", borderRadius: 999, background: "#F1F5F9", border: "1px solid #E2E8F0", color: "#475569", fontSize: 13, fontWeight: 600 }}>{s}</span>
          ))}
        </div>
      </div>

      {/* ── Recursos ── */}
      <section id="recursos" style={{ maxWidth: 1040, margin: "0 auto", padding: "60px 24px 30px", scrollMarginTop: 70 }}>
        <div data-reveal style={{ textAlign: "center", marginBottom: 44 }}>
          <h2 style={{ fontSize: 32, fontWeight: 800, letterSpacing: -0.6, margin: "0 0 10px" }}>Tudo para vencer uma licitação</h2>
          <p style={{ fontSize: 16, color: "#64748B", margin: 0 }}>Da descoberta do edital ao lance final — num só lugar.</p>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(290px,1fr))", gap: 18 }}>
          {FEATURES.map((f, i) => (
            <div key={i} data-reveal className="lp-card" style={{ background: "#FFF", border: "1px solid #E2E8F0", borderRadius: 16, padding: 24, transitionDelay: `${i * 50}ms` }}>
              <div className="lp-feat-ic" style={{ width: 46, height: 46, borderRadius: 12, background: "rgba(16,185,129,.1)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 14 }}><f.Ic /></div>
              <div style={{ fontSize: 16.5, fontWeight: 700, marginBottom: 6 }}>{f.t}</div>
              <div style={{ fontSize: 14, color: "#64748B", lineHeight: 1.55 }}>{f.d}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Como funciona ── */}
      <section id="como-funciona" style={{ background: C.light, borderTop: "1px solid #E2E8F0", borderBottom: "1px solid #E2E8F0", padding: "72px 24px", marginTop: 50 }}>
        <div style={{ maxWidth: 900, margin: "0 auto", textAlign: "center" }}>
          <div data-reveal>
            <h2 style={{ fontSize: 32, fontWeight: 800, letterSpacing: -0.6, margin: "0 0 10px" }}>Como funciona</h2>
            <p style={{ fontSize: 16, color: "#64748B", margin: "0 0 46px" }}>Quatro passos para automatizar suas licitações.</p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px,1fr))", gap: 26 }}>
            {STEPS.map((s, i) => (
              <div key={i} data-reveal style={{ textAlign: "center", transitionDelay: `${i * 70}ms` }}>
                <div style={{ width: 50, height: 50, borderRadius: "50%", background: `linear-gradient(135deg, ${C.green}, ${C.blue})`, color: "#06281E", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 19, fontWeight: 800, marginBottom: 14 }}>{s.n}</div>
                <div style={{ fontSize: 15.5, fontWeight: 700, marginBottom: 5 }}>{s.t}</div>
                <div style={{ fontSize: 13.5, color: "#64748B", lineHeight: 1.5 }}>{s.d}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Comparativo Sem vs Com ── */}
      <section style={{ maxWidth: 920, margin: "0 auto", padding: "76px 24px 30px" }}>
        <div data-reveal style={{ textAlign: "center", marginBottom: 40 }}>
          <h2 style={{ fontSize: 32, fontWeight: 800, letterSpacing: -0.6, margin: "0 0 10px" }}>O dia a dia muda de figura</h2>
          <p style={{ fontSize: 16, color: "#64748B", margin: 0 }}>Do trabalho manual e disperso para um fluxo único e automático.</p>
        </div>
        <div className="lp-compara" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
          <div data-reveal style={{ background: "#FFF", border: "1px solid #E2E8F0", borderRadius: 16, padding: 26 }}>
            <div style={{ fontSize: 13, fontWeight: 800, color: "#EF4444", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 16 }}>Do jeito manual</div>
            {COMPARA.sem.map((t, i) => (
              <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 11, padding: "9px 0", borderTop: i ? "1px solid #F1F5F9" : "none" }}>
                <span style={{ width: 20, height: 20, borderRadius: "50%", background: "#FEE2E2", color: "#EF4444", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 800, flexShrink: 0, marginTop: 1 }}>×</span>
                <span style={{ fontSize: 14, color: "#475569", lineHeight: 1.5 }}>{t}</span>
              </div>
            ))}
          </div>
          <div data-reveal className="lp-card" style={{ background: C.ink, border: "1px solid transparent", borderRadius: 16, padding: 26, boxShadow: "0 24px 60px rgba(2,6,23,.25)" }}>
            <div style={{ fontSize: 13, fontWeight: 800, color: C.greenSoft, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
              Com Licitações<span style={{ color: "#FFF" }}>AI</span>
            </div>
            {COMPARA.com.map((t, i) => (
              <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 11, padding: "9px 0", borderTop: i ? "1px solid rgba(255,255,255,.06)" : "none" }}>
                <span style={{ width: 20, height: 20, borderRadius: "50%", background: "rgba(16,185,129,.15)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 1 }}>{IconCheck(C.greenSoft, 13)}</span>
                <span style={{ fontSize: 14, color: "#CBD5E1", lineHeight: 1.5 }}>{t}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Planos ── */}
      <section id="planos" style={{ maxWidth: 1000, margin: "0 auto", padding: "76px 24px", scrollMarginTop: 70 }}>
        <div data-reveal style={{ textAlign: "center", marginBottom: 44 }}>
          <h2 style={{ fontSize: 32, fontWeight: 800, letterSpacing: -0.6, margin: "0 0 10px" }}>Planos</h2>
          <p style={{ fontSize: 16, color: "#64748B", margin: 0 }}>Escolha o ideal para sua empresa. Cancele quando quiser.</p>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(270px,1fr))", gap: 20, alignItems: "start" }}>
          {PLANS.map((p, i) => (
            <div key={i} data-reveal className="lp-card" style={{
              background: p.hi ? C.ink : "#FFF", color: p.hi ? "#FFF" : C.ink, borderRadius: 18, padding: 30, position: "relative",
              border: p.hi ? "1px solid transparent" : "1px solid #E2E8F0", boxShadow: p.hi ? "0 24px 60px rgba(2,6,23,.25)" : "none",
              transform: p.hi ? "scale(1.03)" : "none", transitionDelay: `${i * 60}ms`,
            }}>
              {p.hi && <div style={{ position: "absolute", top: -13, left: "50%", transform: "translateX(-50%)", background: `linear-gradient(135deg, ${C.green}, ${C.greenSoft})`, color: "#06281E", padding: "4px 16px", borderRadius: 999, fontSize: 11.5, fontWeight: 800, letterSpacing: 0.3 }}>MAIS POPULAR</div>}
              <div style={{ fontSize: 17, fontWeight: 800, marginBottom: 4 }}>{p.name}</div>
              <div style={{ fontSize: 13, color: p.hi ? C.mut : "#64748B", marginBottom: 18 }}>{p.desc}</div>
              <div style={{ marginBottom: 22 }}>
                <span style={{ fontSize: 36, fontWeight: 800, letterSpacing: -1 }}>{p.price}</span>
                {p.period && <span style={{ fontSize: 14, color: p.hi ? C.mut : "#94A3B8" }}> {p.period}</span>}
              </div>
              <ul style={{ listStyle: "none", padding: 0, margin: "0 0 26px" }}>
                {p.features.map((f, j) => (
                  <li key={j} style={{ fontSize: 13.5, color: p.hi ? "#CBD5E1" : "#334155", padding: "5px 0", display: "flex", alignItems: "center", gap: 9 }}>{IconCheck(p.hi ? C.greenSoft : C.green)} {f}</li>
                ))}
              </ul>
              <button className="lp-btn" onClick={onStart} style={{ width: "100%", padding: "12px 0", borderRadius: 11, fontSize: 14.5, fontWeight: 700, cursor: "pointer", border: "none", background: p.hi ? `linear-gradient(135deg, ${C.green}, ${C.greenSoft})` : "#0B1220", color: p.hi ? "#06281E" : "#FFF" }}>{p.cta}</button>
            </div>
          ))}
        </div>
      </section>

      {/* ── FAQ ── */}
      <section id="faq" style={{ background: C.light, borderTop: "1px solid #E2E8F0", padding: "72px 24px", scrollMarginTop: 70 }}>
        <div style={{ maxWidth: 760, margin: "0 auto" }}>
          <div data-reveal style={{ textAlign: "center", marginBottom: 38 }}>
            <h2 style={{ fontSize: 32, fontWeight: 800, letterSpacing: -0.6, margin: "0 0 10px" }}>Perguntas frequentes</h2>
            <p style={{ fontSize: 16, color: "#64748B", margin: 0 }}>O essencial antes de começar.</p>
          </div>
          {FAQ.map((f, i) => {
            const open = faqOpen === i;
            return (
              <div key={i} data-reveal className="lp-faq" style={{ background: "#FFF", border: "1px solid #E2E8F0", borderRadius: 12, marginBottom: 10, overflow: "hidden" }}>
                <button onClick={() => setFaqOpen(open ? -1 : i)} style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "16px 20px", background: "transparent", border: "none", cursor: "pointer", textAlign: "left" }}>
                  <span style={{ fontSize: 15, fontWeight: 700, color: C.ink }}>{f.q}</span>
                  <span style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .2s ease", flexShrink: 0 }}>{IconChevron("#64748B")}</span>
                </button>
                <div style={{ maxHeight: open ? 200 : 0, transition: "max-height .28s ease", overflow: "hidden" }}>
                  <div style={{ padding: "0 20px 18px", fontSize: 14, color: "#64748B", lineHeight: 1.6 }}>{f.a}</div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── CTA final ── */}
      <section style={{ background: `radial-gradient(800px 320px at 50% 0%, rgba(96,165,250,.18), transparent 60%), ${C.ink}`, padding: "74px 24px", textAlign: "center" }}>
        <div data-reveal>
          <h2 style={{ fontSize: 30, fontWeight: 800, letterSpacing: -0.6, color: "#FFF", margin: "0 0 12px" }}>Pronto para ganhar mais licitações?</h2>
          <p style={{ fontSize: 15.5, color: C.mut, margin: "0 0 26px" }}>Cadastre sua empresa e comece a monitorar editais hoje.</p>
          <button className="lp-btn lp-glow" onClick={onStart} style={{ padding: "14px 36px", color: "#06281E", border: "none", borderRadius: 12, fontSize: 15.5, fontWeight: 800, cursor: "pointer" }}>Criar conta gratuita</button>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer style={{ background: C.ink, borderTop: `1px solid ${C.line}`, padding: "26px 24px", textAlign: "center" }}>
        <div style={{ color: C.mut, fontSize: 13 }}>
          <span style={{ color: "#FFF", fontWeight: 700 }}>Licitações<span style={{ color: C.greenSoft }}>AI</span></span> · Monitoramento de licitações públicas · Dados do PNCP
        </div>
      </footer>
    </div>
  );
}
