import { useState, useEffect } from "react";
import { useAuth } from "../AuthContext";

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

// SVG icons inline pra não depender de lib
const ICON = {
  home: <path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1h-5v-7h-6v7H4a1 1 0 01-1-1V9.5z" />,
  pipeline: <path d="M3 5h7v6H3V5zm0 8h7v6H3v-6zm9-8h9v3h-9V5zm0 5h9v3h-9v-3zm0 5h9v4h-9v-4z" />,
  buscar: <path d="M11 18a7 7 0 100-14 7 7 0 000 14zm5.5-1.5L21 21" />,
  radar: <g>
    <circle cx="12" cy="12" r="2.5" />
    <path d="M12 2v5M12 17v5M2 12h5M17 12h5" />
    <circle cx="12" cy="12" r="6" />
    <circle cx="12" cy="12" r="10" opacity="0.3" />
  </g>,
  disputa: <path d="M5 15l6-6 3 3 5-5M5 15l3 3M14 12l3 3M3 21h18" />,
  planilha: <path d="M4 4h16v16H4V4zm0 5h16M9 4v16" />,
  habilitacao: <path d="M12 2l9 4v6c0 5-3.5 9-9 10-5.5-1-9-5-9-10V6l9-4zm-1 13l5-5-1.5-1.5L11 12l-1.5-1.5L8 12l3 3z" />,
  bi: <path d="M3 21h18M5 21V11m4 10V7m4 14V3m4 18v-7m4 7v-4" />,
  empresa: <path d="M3 21h18M5 21V7l7-4 7 4v14M9 21v-5h6v5M9 11h2m2 0h2M9 14h2m2 0h2" />,
  admin: <g>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
  </g>,
  logout: <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" />,
};

function Icon({ name, size = 18, stroke = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      {ICON[name]}
    </svg>
  );
}

const PRODUTOS_PRINCIPAIS = [
  { key: "home", label: "Home", path: "/", icon: "home" },
  { key: "pipeline", label: "Pipeline", path: "/pipeline", icon: "pipeline" },
  { key: "buscar", label: "Buscar PNCP", path: "/buscar", icon: "buscar" },
  { key: "radar", label: "Radar", path: "/radar", icon: "radar" },
  { key: "pregoes", label: "Disputa", path: "/pregoes", icon: "disputa" },
  { key: "planilhas", label: "Proposta", path: "/planilhas", icon: "planilha" },
  { key: "habilitacao", label: "Habilitação", path: "/habilitacao", icon: "habilitacao" },
  { key: "concorrentes", label: "BI", path: "/concorrentes", icon: "bi" },
  { key: "perfil", label: "Empresa", path: "/perfil", icon: "empresa" },
];

export default function Sidebar({ ativo, isAdmin }) {
  const [expandido, setExpandido] = useState(() => {
    try { return localStorage.getItem("sidebar_expandido") === "1"; } catch { return false; }
  });
  const { logout } = useAuth();

  const toggle = () => {
    const novo = !expandido;
    setExpandido(novo);
    try { localStorage.setItem("sidebar_expandido", novo ? "1" : "0"); } catch {}
  };

  const w = expandido ? 200 : 56;
  const itens = isAdmin ? [...PRODUTOS_PRINCIPAIS, { key: "admin", label: "Admin", path: "/admin", icon: "admin" }] : PRODUTOS_PRINCIPAIS;

  return (
    <aside style={{
      position: "fixed", left: 0, top: 0, bottom: 0, width: w,
      background: C.s1, borderRight: `1px solid ${C.b1}`,
      display: "flex", flexDirection: "column",
      transition: "width 0.18s ease", zIndex: 50, overflow: "hidden",
    }}>
      <div style={{ padding: "14px 16px", display: "flex", alignItems: "center", gap: 12, borderBottom: `1px solid ${C.b1}`, minHeight: 56 }}>
        <button onClick={toggle} title={expandido ? "Recolher" : "Expandir"}
          style={{ background: "transparent", border: 0, color: C.t2, cursor: "pointer", padding: 0, display: "flex", alignItems: "center" }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M3 6h18M3 12h18M3 18h18" />
          </svg>
        </button>
        {expandido && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: C.ac, animation: "livePulse 2s infinite" }} />
            <span style={{ fontSize: 13, fontWeight: 700, color: C.t1, letterSpacing: -0.3, whiteSpace: "nowrap" }}>Licitações AI</span>
          </div>
        )}
      </div>

      <nav style={{ flex: 1, padding: "8px 0", display: "flex", flexDirection: "column", gap: 2, overflowY: "auto" }}>
        {itens.map(item => {
          const sel = ativo === item.key;
          return (
            <button key={item.key} onClick={() => navegar(item.path)}
              title={item.label}
              style={{
                background: sel ? C.s3 : "transparent",
                border: 0, borderLeft: sel ? `3px solid ${C.ac}` : "3px solid transparent",
                color: sel ? C.t1 : C.t2,
                padding: "10px 16px 10px 13px",
                cursor: "pointer", display: "flex", alignItems: "center", gap: 14,
                width: "100%", textAlign: "left", fontFamily: "inherit",
                transition: "background 0.12s, color 0.12s",
              }}
              onMouseEnter={e => { if (!sel) e.currentTarget.style.background = C.s2; }}
              onMouseLeave={e => { if (!sel) e.currentTarget.style.background = "transparent"; }}>
              <Icon name={item.icon} size={18} />
              {expandido && (
                <span style={{ fontSize: 12, fontWeight: 600, letterSpacing: 0.2, whiteSpace: "nowrap" }}>
                  {item.label}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div style={{ padding: "8px 0", borderTop: `1px solid ${C.b1}` }}>
        <button onClick={logout} title="Sair"
          style={{
            background: "transparent", border: 0, color: C.t2,
            padding: "10px 16px 10px 16px",
            cursor: "pointer", display: "flex", alignItems: "center", gap: 14,
            width: "100%", textAlign: "left", fontFamily: "inherit",
          }}
          onMouseEnter={e => e.currentTarget.style.color = C.rd}
          onMouseLeave={e => e.currentTarget.style.color = C.t2}>
          <Icon name="logout" size={18} />
          {expandido && <span style={{ fontSize: 12, fontWeight: 600, whiteSpace: "nowrap" }}>Sair</span>}
        </button>
      </div>
    </aside>
  );
}

export const SIDEBAR_WIDTH_COLLAPSED = 56;
export const SIDEBAR_WIDTH_EXPANDED = 200;
