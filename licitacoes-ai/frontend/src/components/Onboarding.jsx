import { useState, useEffect } from "react";
import { useAuth } from "../AuthContext";

const C = {
  ink: "#0B1220", inkSoft: "#111A2B", line: "#1E293B",
  green: "#10B981", greenSoft: "#34D399", blue: "#60A5FA", mut: "#94A3B8",
};

const UFS = ["AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT","PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"];

const ICONES = { mao_obra: "👥", obras: "🏗️", aquisicao: "📦", residuos: "♻️" };

export default function Onboarding() {
  const { tenant, token, login } = useAuth();
  const [tipos, setTipos] = useState([]);
  const [step, setStep] = useState(1);
  const [tipo, setTipo] = useState(null);     // objeto do tipo escolhido
  const [nichos, setNichos] = useState([]);   // keys de nicho
  const [ufs, setUfs] = useState(["RJ"]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/onboarding/opcoes")
      .then(r => r.json())
      .then(d => setTipos(d.tipos || []))
      .catch(() => {});
  }, []);

  const escolherTipo = (t) => {
    setTipo(t);
    setNichos(t.nichos.map(n => n.key)); // já marca todos do tipo por padrão
    setStep(2);
  };

  const toggleNicho = (k) => setNichos(p => p.includes(k) ? p.filter(x => x !== k) : [...p, k]);
  const toggleUf = (u) => setUfs(p => p.includes(u) ? p.filter(x => x !== u) : [...p, u]);

  const concluir = async () => {
    setError(""); setLoading(true);
    try {
      const r = await fetch("/api/onboarding/configurar", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ tipo_negocio: tipo.key, nichos, ufs }),
      });
      const d = await r.json();
      if (!r.ok || !d.ok) throw new Error(d.erro || "Erro ao salvar");
      // Atualiza o tenant → App sai do onboarding e mostra o dashboard
      login({ ...tenant, onboarding_done: 1, tipo_negocio: tipo.key }, token);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  };

  const card = { background: "#FFF", border: "1px solid #E2E8F0", borderRadius: 14, cursor: "pointer", transition: "all .15s ease" };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 24,
      fontFamily: "'DM Sans', system-ui, sans-serif",
      background: `radial-gradient(900px 500px at 50% -10%, rgba(16,185,129,.18), transparent 60%), linear-gradient(180deg, ${C.ink}, ${C.inkSoft})`,
    }}>
      <style>{`
        .ob-tipo:hover{ transform:translateY(-4px); box-shadow:0 18px 40px rgba(2,6,23,.4); border-color:#10B981 !important }
        .ob-chip{ transition:all .12s ease; cursor:pointer }
        .ob-btn{ transition:transform .15s ease, filter .2s ease }
        .ob-btn:hover{ transform:translateY(-2px); filter:brightness(1.05) }
      `}</style>

      <div style={{ width: 680, maxWidth: "100%" }}>
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
            <span style={{ fontSize: 18, fontWeight: 800, color: "#FFF" }}>Licitações<span style={{ color: C.greenSoft }}>AI</span></span>
          </div>
          <div style={{ display: "flex", gap: 6, justifyContent: "center", marginBottom: 18 }}>
            {[1, 2].map(s => (
              <div key={s} style={{ width: 32, height: 4, borderRadius: 2, background: step >= s ? C.green : "rgba(255,255,255,.15)" }} />
            ))}
          </div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: "#FFF", margin: "0 0 8px", letterSpacing: -0.5 }}>
            {step === 1 ? "O que sua empresa faz?" : "Quase lá — afine seu radar"}
          </h1>
          <p style={{ fontSize: 14.5, color: C.mut, margin: 0 }}>
            {step === 1 ? "Isso define quais editais chegam pra você e como calculamos os custos." : `${tipo?.label} · escolha os segmentos e os estados que você atende.`}
          </p>
        </div>

        {/* Step 1 — tipo de negócio */}
        {step === 1 && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px,1fr))", gap: 14 }}>
            {tipos.map(t => (
              <div key={t.key} className="ob-tipo" onClick={() => escolherTipo(t)} style={{ ...card, padding: 22 }}>
                <div style={{ fontSize: 30, marginBottom: 10 }}>{ICONES[t.key] || "•"}</div>
                <div style={{ fontSize: 16.5, fontWeight: 800, color: C.ink, marginBottom: 5 }}>{t.label}</div>
                <div style={{ fontSize: 13, color: "#64748B", lineHeight: 1.5 }}>{t.desc}</div>
              </div>
            ))}
          </div>
        )}

        {/* Step 2 — nichos + UFs */}
        {step === 2 && tipo && (
          <div style={{ background: "#FFF", borderRadius: 16, padding: 28 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#374151", marginBottom: 10 }}>Segmentos que você atende</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 24 }}>
              {tipo.nichos.map(n => {
                const on = nichos.includes(n.key);
                return (
                  <button key={n.key} className="ob-chip" onClick={() => toggleNicho(n.key)}
                    style={{ padding: "8px 15px", borderRadius: 999, fontSize: 13.5, fontWeight: 600, cursor: "pointer",
                      border: on ? "1px solid #10B981" : "1px solid #D8DEE9",
                      background: on ? "rgba(16,185,129,.1)" : "#FFF", color: on ? "#047857" : "#475569" }}>
                    {on ? "✓ " : ""}{n.label}
                  </button>
                );
              })}
            </div>

            <div style={{ fontSize: 13, fontWeight: 700, color: "#374151", marginBottom: 10 }}>Estados (UF) que você atende</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 22 }}>
              {UFS.map(u => {
                const on = ufs.includes(u);
                return (
                  <button key={u} className="ob-chip" onClick={() => toggleUf(u)}
                    style={{ width: 42, padding: "7px 0", borderRadius: 8, fontSize: 12.5, fontWeight: 700, cursor: "pointer",
                      border: on ? "1px solid #10B981" : "1px solid #E2E8F0",
                      background: on ? "#10B981" : "#FFF", color: on ? "#06281E" : "#94A3B8" }}>
                    {u}
                  </button>
                );
              })}
            </div>

            {error && <div style={{ color: "#DC2626", fontSize: 13, marginBottom: 12 }}>{error}</div>}

            <div style={{ display: "flex", gap: 10 }}>
              <button onClick={() => setStep(1)} style={{ padding: "12px 20px", background: "#F1F5F9", color: "#475569", border: "none", borderRadius: 11, fontSize: 14, fontWeight: 700, cursor: "pointer" }}>Voltar</button>
              <button onClick={concluir} disabled={loading || nichos.length === 0 || ufs.length === 0} className="ob-btn"
                style={{ flex: 1, padding: "12px 0", background: `linear-gradient(135deg, ${C.green}, ${C.greenSoft})`, color: "#06281E", border: "none", borderRadius: 11, fontSize: 14.5, fontWeight: 800, cursor: "pointer", opacity: (loading || nichos.length === 0 || ufs.length === 0) ? 0.5 : 1 }}>
                {loading ? "Configurando…" : "Concluir e ver meus editais →"}
              </button>
            </div>
          </div>
        )}

        <div style={{ textAlign: "center", marginTop: 18, fontSize: 12.5, color: C.mut }}>
          Você pode mudar isso depois nas configurações.
        </div>
      </div>
    </div>
  );
}
