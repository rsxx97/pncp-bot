import { useAuth } from "../AuthContext";
import Sidebar, { SIDEBAR_WIDTH_COLLAPSED, SIDEBAR_WIDTH_EXPANDED } from "./Sidebar";
import LogoProduto from "./LogoProduto";
import { useState, useEffect } from "react";

const C = {
  bg: "#09090B", s1: "#111114", s2: "#18181C", s3: "#222228",
  b1: "#2A2A32", b2: "#3A3A44",
  t1: "#EEEEE8", t2: "#98968E", t3: "#5A5854",
  ac: "#BEFF3A", rd: "#FF4D4D", am: "#FFB038", tl: "#2EDDA8", bl: "#5A9EF7",
};
const mono = "'JetBrains Mono', monospace";

export default function AppLayout({ produto, titulo, subtitulo, children, badge }) {
  const { tenant, isAdmin } = useAuth();
  const [sidebarW, setSidebarW] = useState(() => {
    try { return localStorage.getItem("sidebar_expandido") === "1" ? SIDEBAR_WIDTH_EXPANDED : SIDEBAR_WIDTH_COLLAPSED; } catch { return SIDEBAR_WIDTH_COLLAPSED; }
  });

  useEffect(() => {
    const onStorage = () => {
      const exp = localStorage.getItem("sidebar_expandido") === "1";
      setSidebarW(exp ? SIDEBAR_WIDTH_EXPANDED : SIDEBAR_WIDTH_COLLAPSED);
    };
    window.addEventListener("storage", onStorage);
    // Reage também a mudanças no mesmo tab (sidebar dispara um evento custom)
    const id = setInterval(onStorage, 200);
    return () => { window.removeEventListener("storage", onStorage); clearInterval(id); };
  }, []);

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

      <Sidebar ativo={produto} isAdmin={isAdmin} />

      <main style={{ marginLeft: sidebarW, transition: "margin-left 0.18s ease", position: "relative", zIndex: 1 }}>
        <div style={{ borderBottom: `1px solid ${C.b1}`, padding: "14px 28px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, background: `${C.s1}40`, backdropFilter: "blur(8px)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
            <LogoProduto produto={produto} size={32} />
            {badge}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {tenant && (
              <span style={{ fontFamily: mono, fontSize: 10, color: C.t3, padding: "4px 10px", border: `1px solid ${C.b1}`, borderRadius: 4 }}>
                {tenant.nome_empresa}
              </span>
            )}
          </div>
        </div>

        <div style={{ padding: "24px 28px", maxWidth: 1500, margin: "0 auto" }}>
          {children}
        </div>
      </main>
    </div>
  );
}
