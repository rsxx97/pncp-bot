import { useState } from "react";

/* Paleta — mesma da Landing */
const C = {
  ink: "#0B1220", inkSoft: "#111A2B", line: "#1E293B",
  green: "#10B981", greenSoft: "#34D399", blue: "#60A5FA",
  txt: "#E5E9F0", mut: "#94A3B8",
};

const Icon = ({ d, size = 20, stroke = C.green, sw = 1.8 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">{d}</svg>
);
const IconSearch = (c, s) => <Icon stroke={c} size={s} d={<><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></>} />;
const IconCheck = (c = C.greenSoft, s = 16) => <Icon size={s} stroke={c} d={<path d="M20 6 9 17l-5-5" />} />;

const BENEFICIOS = [
  "Monitoramento automático do PNCP (27 UFs)",
  "Análise de editais com IA — direto do PDF",
  "Planilhas de custo competitivas (BDI e encargos)",
  "Radar de disputa ao vivo: chat, lances e fase",
];

export default function Login({ onLogin }) {
  const [mode, setMode] = useState("login"); // login | register
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [nome, setNome] = useState("");
  const [cnpj, setCnpj] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(""); setInfo("");
    setLoading(true);

    const url = mode === "login" ? "/api/auth/login" : "/api/auth/register";
    const body = mode === "login"
      ? { email, senha }
      : { email, senha, nome_empresa: nome, cnpj: cnpj || null };

    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await resp.json();
      if (!resp.ok) {
        const msg = typeof data.detail === "string" ? data.detail : Array.isArray(data.detail) ? data.detail.map(d => d.msg).join(", ") : "Erro desconhecido";
        throw new Error(msg);
      }
      // Cadastro novo já devolve token (login automático). Se vier sem token (fluxo antigo), mostra aviso.
      if (!data.token) {
        setInfo(data.message || "Cadastro realizado. Verifique seu e-mail.");
        setMode("login");
        setLoading(false);
        return;
      }
      localStorage.setItem("token", data.token);
      localStorage.setItem("tenant", JSON.stringify(data.tenant));
      onLogin(data.tenant, data.token);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const inputStyle = {
    width: "100%", padding: "11px 14px", border: "1px solid #D8DEE9", borderRadius: 10,
    fontSize: 14.5, outline: "none", boxSizing: "border-box", fontFamily: "inherit", color: C.ink,
    background: "#FFF", transition: "border-color .15s ease, box-shadow .15s ease",
  };
  const label = { fontSize: 12.5, fontWeight: 700, color: "#374151", display: "block", marginBottom: 6 };

  const isLogin = mode === "login";

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 24,
      fontFamily: "'DM Sans', system-ui, sans-serif",
      background: `radial-gradient(900px 500px at 50% -10%, rgba(16,185,129,.18), transparent 60%), radial-gradient(800px 460px at 90% 20%, rgba(96,165,250,.12), transparent 55%), linear-gradient(180deg, ${C.ink}, ${C.inkSoft})`,
    }}>
      <style>{`
        @keyframes alFade { from {opacity:0; transform:translateY(12px)} to {opacity:1; transform:none} }
        .al-shell{ animation: alFade .5s ease both }
        .al-input:focus{ border-color:#10B981 !important; box-shadow:0 0 0 3px rgba(16,185,129,.15) }
        .al-btn{ transition: transform .15s ease, filter .2s ease }
        .al-btn:hover{ transform:translateY(-2px); filter:brightness(1.05) }
        .al-btn:active{ transform:translateY(0) }
        .al-link{ background:none; border:none; color:#10B981; font-size:13.5px; font-weight:700; cursor:pointer; font-family:inherit }
        .al-link:hover{ text-decoration:underline }
        @media (max-width: 760px){ .al-brand{ display:none !important } .al-shell{ width:420px !important } }
      `}</style>

      <div className="al-shell" style={{
        display: "flex", width: 900, maxWidth: "100%", background: "#FFF",
        borderRadius: 22, overflow: "hidden", boxShadow: "0 40px 100px rgba(2,6,23,.55)",
      }}>
        {/* ── Painel da marca (esquerda) ── */}
        <div className="al-brand" style={{
          flex: "1 1 0", position: "relative", padding: 40, color: "#FFF", overflow: "hidden",
          background: `radial-gradient(600px 300px at 20% 0%, rgba(16,185,129,.22), transparent 60%), linear-gradient(160deg, ${C.ink}, ${C.inkSoft})`,
          display: "flex", flexDirection: "column", justifyContent: "space-between",
        }}>
          <div style={{ position: "absolute", width: 260, height: 260, borderRadius: "50%", background: "rgba(96,165,250,.14)", filter: "blur(70px)", bottom: -50, right: -40 }} />
          <div style={{ position: "relative", zIndex: 2 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 34 }}>
              <div style={{ width: 34, height: 34, borderRadius: 10, background: `linear-gradient(135deg, ${C.green}, ${C.greenSoft})`, display: "flex", alignItems: "center", justifyContent: "center" }}>{IconSearch("#06281E", 20)}</div>
              <span style={{ fontSize: 18, fontWeight: 800, letterSpacing: -0.3 }}>Licitações<span style={{ color: C.greenSoft }}>AI</span></span>
            </div>
            <h2 style={{ fontSize: 25, fontWeight: 800, lineHeight: 1.2, letterSpacing: -0.6, margin: "0 0 14px" }}>
              Encontre a licitação certa <span style={{ background: `linear-gradient(120deg, ${C.greenSoft}, ${C.blue})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>antes dos concorrentes</span>
            </h2>
            <p style={{ fontSize: 14.5, color: C.mut, lineHeight: 1.6, margin: "0 0 26px" }}>
              Da descoberta do edital ao lance final — tudo num só lugar.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
              {BENEFICIOS.map((b, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 11 }}>
                  <span style={{ width: 22, height: 22, borderRadius: "50%", background: "rgba(16,185,129,.15)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>{IconCheck(C.greenSoft, 14)}</span>
                  <span style={{ fontSize: 13.5, color: "#CBD5E1" }}>{b}</span>
                </div>
              ))}
            </div>
          </div>
          <div style={{ position: "relative", zIndex: 2, display: "flex", gap: 20, marginTop: 30, color: C.mut, fontSize: 12.5 }}>
            <span><b style={{ color: "#FFF" }}>+700</b> editais</span>
            <span><b style={{ color: "#FFF" }}>27</b> UFs</span>
            <span><b style={{ color: "#FFF" }}>Tempo real</b></span>
          </div>
        </div>

        {/* ── Formulário (direita) ── */}
        <div style={{ flex: "1 1 0", padding: "44px 40px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <h1 style={{ fontSize: 23, fontWeight: 800, color: C.ink, margin: "0 0 4px", letterSpacing: -0.4 }}>
            {isLogin ? "Acesse sua conta" : "Crie sua conta grátis"}
          </h1>
          <p style={{ fontSize: 13.5, color: "#6B7280", margin: "0 0 24px" }}>
            {isLogin ? "Bem-vindo de volta." : "Sem cartão de crédito. Configure em 5 minutos."}
          </p>

          <form onSubmit={handleSubmit}>
            {!isLogin && (
              <>
                <div style={{ marginBottom: 14 }}>
                  <label style={label}>Nome da empresa</label>
                  <input className="al-input" style={inputStyle} value={nome} onChange={e => setNome(e.target.value)} placeholder="Ex: Minha Empresa Ltda" required />
                </div>
                <div style={{ marginBottom: 14 }}>
                  <label style={label}>CNPJ <span style={{ color: "#9CA3AF", fontWeight: 500 }}>(opcional)</span></label>
                  <input className="al-input" style={inputStyle} value={cnpj} onChange={e => setCnpj(e.target.value)} placeholder="00.000.000/0001-00" />
                </div>
              </>
            )}

            <div style={{ marginBottom: 14 }}>
              <label style={label}>E-mail</label>
              <input className="al-input" style={inputStyle} type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="seu@email.com" required />
            </div>

            <div style={{ marginBottom: 18 }}>
              <label style={label}>Senha</label>
              <input className="al-input" style={inputStyle} type="password" value={senha} onChange={e => setSenha(e.target.value)} placeholder={isLogin ? "Sua senha" : "Mínimo 6 caracteres"} required minLength={6} />
            </div>

            {error && <div style={{ background: "#FEF2F2", border: "1px solid #FECACA", color: "#DC2626", fontSize: 13, padding: "9px 12px", borderRadius: 9, marginBottom: 14 }}>{error}</div>}
            {info && <div style={{ background: "#ECFDF5", border: "1px solid #A7F3D0", color: "#047857", fontSize: 13, padding: "9px 12px", borderRadius: 9, marginBottom: 14 }}>{info}</div>}

            <button type="submit" disabled={loading} className="al-btn"
              style={{ width: "100%", padding: "12px 0", background: `linear-gradient(135deg, ${C.green}, ${C.greenSoft})`, color: "#06281E", border: "none", borderRadius: 11, fontSize: 14.5, fontWeight: 800, cursor: loading ? "default" : "pointer", opacity: loading ? 0.7 : 1 }}>
              {loading ? "Aguarde…" : isLogin ? "Entrar" : "Criar conta grátis"}
            </button>
          </form>

          <div style={{ textAlign: "center", marginTop: 20, fontSize: 13.5, color: "#6B7280" }}>
            {isLogin ? "Não tem conta? " : "Já tem conta? "}
            <button className="al-link" onClick={() => { setMode(isLogin ? "register" : "login"); setError(""); setInfo(""); }}>
              {isLogin ? "Cadastre-se grátis" : "Faça login"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
