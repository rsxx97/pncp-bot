import { useState, useEffect, useCallback } from "react";
import { api } from "./api";
import KPIDashboard from "./components/KPIDashboard";
import EditalTable from "./components/EditalTable";
import EditalDetailPanel from "./components/EditalDetail";
import PncpSearch from "./components/PncpSearch";
import Perfil from "./components/Perfil";
import ConcorrentePanel from "./components/ConcorrentePanel";
import PregaoPanel from "./components/PregaoPanel";
import Login from "./components/Login";

const C = {
  bg: "#09090B", s1: "#111114", s2: "#18181C", s3: "#222228",
  b1: "#2A2A32", b2: "#3A3A44",
  t1: "#EEEEE8", t2: "#98968E", t3: "#5A5854",
  ac: "#BEFF3A", rd: "#FF4D4D", am: "#FFB038", tl: "#2EDDA8", bl: "#5A9EF7",
};

const mono = "'JetBrains Mono', monospace";

function Dashboard({ onLogout }) {
  const [editais, setEditais] = useState([]);
  const [totalEditais, setTotalEditais] = useState(0);
  const [filter, setFilter] = useState("todos");
  const [selectedPncpId, setSelectedPncpId] = useState(null);
  const [tab, setTab] = useState("pipeline");
  const [searchText, setSearchText] = useState("");
  const [period, setPeriod] = useState("90d");

  const statusMap = {
    todos: [],
    novo: ["novo", "classificado"],
    go: ["analisado", "go", "go_com_ressalvas", "go_sem_ressalvas"],
    pronto: ["precificado", "competitivo_pronto"],
  };

  const loadEditais = useCallback(async () => {
    try {
      const params = { per_page: 50, sort: "-score_relevancia" };
      if (filter !== "todos") params.status = statusMap[filter];
      const data = await api.getEditais(params);
      setEditais(data.items);
      setTotalEditais(data.total);
    } catch (e) { console.error(e); }
  }, [filter]);

  useEffect(() => { loadEditais(); }, [filter, loadEditais]);

  const filters = [
    { key: "todos", label: "Todos", count: totalEditais },
    { key: "novo", label: "Novos", count: editais.filter(e => e.status === "novo" || e.status === "classificado").length },
    { key: "go", label: "Go", count: editais.filter(e => (e.parecer || e.status || "").startsWith("go") || e.status === "analisado").length },
    { key: "pronto", label: "Prontos", count: editais.filter(e => ["precificado", "competitivo_pronto"].includes(e.status)).length },
  ];

  return (
    <div style={{ fontFamily: "'Instrument Sans', 'DM Sans', sans-serif", color: C.t1, background: C.bg, minHeight: "100vh", position: "relative", overflow: "hidden" }}>
      {/* Orbs de glow */}
      <div style={{ position: "fixed", top: -200, left: -200, width: 600, height: 600, borderRadius: "50%", background: `radial-gradient(circle, ${C.ac}08, transparent 70%)`, pointerEvents: "none", animation: "breathe 8s ease-in-out infinite" }} />
      <div style={{ position: "fixed", top: "40%", right: -300, width: 700, height: 700, borderRadius: "50%", background: `radial-gradient(circle, ${C.tl}06, transparent 70%)`, pointerEvents: "none", animation: "breathe 10s ease-in-out infinite 2s" }} />
      <div style={{ position: "fixed", bottom: -200, left: "30%", width: 500, height: 500, borderRadius: "50%", background: `radial-gradient(circle, ${C.bl}05, transparent 70%)`, pointerEvents: "none", animation: "breathe 12s ease-in-out infinite 4s" }} />

      <style>{`
        @keyframes breathe { 0%,100% { opacity: 0.04 } 50% { opacity: 0.08 } }
        @keyframes livePulse { 0%,100% { box-shadow: 0 0 0 0 rgba(190,255,58,0.4) } 50% { box-shadow: 0 0 0 6px rgba(190,255,58,0) } }
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
        body { margin: 0; background: ${C.bg}; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: ${C.s2}; }
        ::-webkit-scrollbar-thumb { background: ${C.b2}; border-radius: 3px; }
      `}</style>

      <div style={{ maxWidth: 1060, margin: "0 auto", padding: "0 16px", position: "relative", zIndex: 1 }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "20px 0 24px", flexWrap: "wrap", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: C.ac, animation: "livePulse 2s infinite" }} />
            <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0, letterSpacing: -0.5, color: C.t1 }}>Licitações AI</h1>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {["7d", "30d", "90d", "YTD"].map(p => (
              <button key={p} onClick={() => setPeriod(p.toLowerCase())}
                style={{
                  fontFamily: mono, fontSize: 10, padding: "4px 10px", borderRadius: 6, cursor: "pointer", border: "none",
                  background: period === p.toLowerCase() ? C.s3 : "transparent",
                  color: period === p.toLowerCase() ? C.t1 : C.t3,
                  fontWeight: 600,
                }}>
                {p}
              </button>
            ))}
          </div>
        </div>

        {/* KPI Dashboard */}
        <KPIDashboard period={period} />

        {/* Tab navigation */}
        <div style={{ display: "flex", gap: 4, marginBottom: 16, borderBottom: `1px solid ${C.b1}`, paddingBottom: 0 }}>
          {[
            { key: "pipeline", label: "Pipeline" },
            { key: "buscar", label: "Oportunidades" },
            { key: "pregoes", label: "Pregões" },
            { key: "concorrentes", label: "Concorrentes" },
            { key: "perfil", label: "Empresas" },
          ].map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              style={{
                fontFamily: mono, fontSize: 11, padding: "8px 16px", cursor: "pointer", fontWeight: 600, border: "none",
                borderBottom: tab === t.key ? `2px solid ${C.ac}` : "2px solid transparent",
                background: "none", color: tab === t.key ? C.t1 : C.t3, marginBottom: -1,
                textTransform: "uppercase", letterSpacing: 1,
              }}>
              {t.label}
            </button>
          ))}
        </div>

        {tab === "pipeline" && (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 10 }}>
              <div style={{ display: "flex", gap: 6 }}>
                {filters.map(f => (
                  <button key={f.key} onClick={() => setFilter(f.key)}
                    style={{
                      fontFamily: mono, fontSize: 10, padding: "5px 12px", borderRadius: 6, cursor: "pointer", fontWeight: 600,
                      border: `1px solid ${filter === f.key ? C.b2 : C.b1}`,
                      background: filter === f.key ? C.s3 : "transparent",
                      color: filter === f.key ? C.t1 : C.t3,
                    }}>
                    {f.label} ({f.count})
                  </button>
                ))}
              </div>
            </div>
            <div style={{ marginBottom: 10 }}>
              <input
                placeholder="Buscar por orgao, objeto, empresa..."
                value={searchText}
                onChange={e => setSearchText(e.target.value)}
                style={{
                  width: "100%", padding: "8px 14px", boxSizing: "border-box", outline: "none",
                  background: C.s2, border: `1px solid ${C.b1}`, borderRadius: 8,
                  fontSize: 12, color: C.t1, fontFamily: mono,
                }}
              />
            </div>
            <div style={{ marginBottom: 24 }}>
              <EditalTable editais={editais.filter(ed => {
                if (!searchText.trim()) return true;
                const s = searchText.toLowerCase();
                return (ed.orgao_nome || "").toLowerCase().includes(s)
                  || (ed.objeto || "").toLowerCase().includes(s)
                  || (ed.empresa_sugerida || "").toLowerCase().includes(s)
                  || (ed.uf || "").toLowerCase().includes(s);
              })} onSelect={setSelectedPncpId} onRefresh={loadEditais} dark />
            </div>
          </>
        )}

        {tab === "buscar" && (
          <PncpSearch onImported={() => { loadEditais(); setTab("pipeline"); }} />
        )}

        {tab === "pregoes" && (
          <PregaoPanel editais={editais} />
        )}

        {tab === "concorrentes" && (
          <ConcorrentePanel />
        )}

        {tab === "perfil" && (
          <Perfil token="local" tenant={{ id: 1, nome_empresa: "Minha Empresa" }} />
        )}

        {selectedPncpId && (
          <EditalDetailPanel pncpId={selectedPncpId} onClose={() => setSelectedPncpId(null)} onRefresh={loadEditais} />
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [tenant, setTenant] = useState(() => {
    try { return JSON.parse(localStorage.getItem("tenant")); } catch { return null; }
  });

  const handleLogin = (data) => {
    localStorage.setItem("token", data.token);
    localStorage.setItem("tenant", JSON.stringify(data.tenant));
    setToken(data.token);
    setTenant(data.tenant);
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("tenant");
    setToken(null);
    setTenant(null);
  };

  if (!token) {
    return <Login onLogin={handleLogin} />;
  }

  return <Dashboard onLogout={handleLogout} />;
}
