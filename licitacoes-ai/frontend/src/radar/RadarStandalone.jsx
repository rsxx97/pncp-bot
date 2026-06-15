import { useAuth } from "../AuthContext";
import RadarRoot from "./RadarRoot";

const C = {
  bg: "#09090B", s1: "#111114", s2: "#18181C", s3: "#222228",
  b1: "#2A2A32", b2: "#3A3A44",
  t1: "#EEEEE8", t2: "#98968E", t3: "#5A5854",
  ac: "#BEFF3A", rd: "#FF4D4D", am: "#FFB038", tl: "#2EDDA8", bl: "#5A9EF7",
};
const mono = "'JetBrains Mono', monospace";

function navegar(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export default function RadarStandalone() {
  const { tenant, logout, isAdmin } = useAuth();

  return (
    <div style={{ fontFamily: "'Instrument Sans', 'DM Sans', sans-serif", color: C.t1, background: C.bg, minHeight: "100vh", position: "relative", overflow: "hidden" }}>
      <div style={{ position: "fixed", top: -200, left: -200, width: 600, height: 600, borderRadius: "50%", background: `radial-gradient(circle, ${C.ac}08, transparent 70%)`, pointerEvents: "none", animation: "breathe 8s ease-in-out infinite" }} />
      <div style={{ position: "fixed", top: "40%", right: -300, width: 700, height: 700, borderRadius: "50%", background: `radial-gradient(circle, ${C.tl}06, transparent 70%)`, pointerEvents: "none", animation: "breathe 10s ease-in-out infinite 2s" }} />

      <style>{`
        @keyframes breathe { 0%,100% { opacity: 0.04 } 50% { opacity: 0.08 } }
        @keyframes livePulse { 0%,100% { box-shadow: 0 0 0 0 rgba(190,255,58,0.4) } 50% { box-shadow: 0 0 0 6px rgba(190,255,58,0) } }
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
        body { margin: 0; background: ${C.bg}; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: ${C.s2}; }
        ::-webkit-scrollbar-thumb { background: ${C.b2}; border-radius: 3px; }
      `}</style>

      <div style={{ maxWidth: 1400, margin: "0 auto", padding: "0 16px", position: "relative", zIndex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "20px 0 16px", flexWrap: "wrap", gap: 12, borderBottom: `1px solid ${C.b1}`, marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: C.ac, animation: "livePulse 2s infinite" }} />
            <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0, letterSpacing: -0.5, color: C.t1 }}>
              Radar <span style={{ color: C.ac }}>·</span> Licitações AI
            </h1>
            {tenant && (
              <span style={{ fontFamily: mono, fontSize: 10, color: C.t3, padding: "3px 8px", border: `1px solid ${C.b1}`, borderRadius: 4 }}>
                {tenant.nome_empresa}{isAdmin ? " · ADMIN" : ""}
              </span>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <button onClick={() => navegar("/")}
              style={{ fontFamily: mono, fontSize: 10, padding: "4px 10px", borderRadius: 6, cursor: "pointer", border: `1px solid ${C.b1}`, background: "transparent", color: C.t2, fontWeight: 600 }}>
              ← Dashboard
            </button>
            <button onClick={logout}
              style={{ fontFamily: mono, fontSize: 10, padding: "4px 10px", borderRadius: 6, cursor: "pointer", border: `1px solid ${C.b1}`, background: "transparent", color: C.t2, fontWeight: 600 }}>
              Sair
            </button>
          </div>
        </div>

        <RadarRoot />
      </div>
    </div>
  );
}
