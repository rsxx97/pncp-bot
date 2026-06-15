// Logo SVG contextual por produto — paridade eLicita (logo muda quando entra no produto).
// Cada logo é um par "mark" (ícone colorido) + "wordmark" (Licitações AI · <Produto>).

const PRODUTO_CONFIG = {
  home: {
    label: "Licitações AI",
    sub: null,
    cor: "#BEFF3A",
    desenho: (cor) => (
      <g stroke={cor} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" fill="none">
        <path d="M3 14L12 5l9 9" />
        <path d="M5 12v8h14v-8" />
      </g>
    ),
  },
  pipeline: {
    label: "Pipeline",
    sub: "Boletim",
    cor: "#5A9EF7",
    desenho: (cor) => (
      <g stroke={cor} strokeWidth="1.8" fill="none">
        <rect x="3" y="4" width="6" height="8" rx="1" />
        <rect x="3" y="14" width="6" height="6" rx="1" />
        <rect x="11" y="4" width="6" height="14" rx="1" />
        <rect x="19" y="4" width="3" height="10" rx="1" />
      </g>
    ),
  },
  buscar: {
    label: "Buscar PNCP",
    sub: null,
    cor: "#FFB038",
    desenho: (cor) => (
      <g stroke={cor} strokeWidth="1.8" fill="none" strokeLinecap="round">
        <circle cx="11" cy="11" r="6" />
        <path d="M16 16l4 4" />
      </g>
    ),
  },
  radar: {
    label: "Radar",
    sub: "Tempo real",
    cor: "#2EDDA8",
    desenho: (cor) => (
      <g fill="none" strokeLinecap="round">
        <circle cx="12" cy="12" r="2" fill={cor} stroke="none" />
        <circle cx="12" cy="12" r="5.5" stroke={cor} strokeWidth="1.6" opacity="0.85" />
        <circle cx="12" cy="12" r="9.5" stroke={cor} strokeWidth="1.6" opacity="0.4" />
        <path d="M12 12 L21 6" stroke={cor} strokeWidth="1.6" />
      </g>
    ),
  },
  pregoes: {
    label: "Disputa",
    sub: "Lances + Robot",
    cor: "#FF4D4D",
    desenho: (cor) => (
      <g fill="none" stroke={cor} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 4l6 6-7 7-6-6 7-7z" />
        <path d="M5 21l4-4" />
        <path d="M3 21h7" />
      </g>
    ),
  },
  planilhas: {
    label: "Proposta",
    sub: "Planilhas + BDI",
    cor: "#A78BFA",
    desenho: (cor) => (
      <g fill="none" stroke={cor} strokeWidth="1.6">
        <rect x="3.5" y="3.5" width="17" height="17" rx="1.5" />
        <path d="M3.5 9H21M3.5 14.5H21M9 3.5V21M14.5 3.5V21" />
      </g>
    ),
  },
  habilitacao: {
    label: "Habilitação",
    sub: "Documentos + CCT",
    cor: "#22C55E",
    desenho: (cor) => (
      <g fill="none" stroke={cor} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 3l8 3.5v5c0 4.7-3.3 8.5-8 9.5-4.7-1-8-4.8-8-9.5v-5L12 3z" />
        <path d="M9 12l2.5 2.5L16 10" />
      </g>
    ),
  },
  concorrentes: {
    label: "BI",
    sub: "Concorrentes + Mercado",
    cor: "#06B6D4",
    desenho: (cor) => (
      <g fill="none" stroke={cor} strokeWidth="1.8" strokeLinecap="round">
        <path d="M3 21h18" />
        <path d="M6 21V12" />
        <path d="M11 21V8" />
        <path d="M16 21V14" />
        <path d="M21 21V4" />
      </g>
    ),
  },
  perfil: {
    label: "Empresa",
    sub: "Cadastro + Integrações",
    cor: "#F472B6",
    desenho: (cor) => (
      <g fill="none" stroke={cor} strokeWidth="1.6" strokeLinejoin="round">
        <path d="M3 21h18" />
        <path d="M5 21V8l7-4 7 4v13" />
        <path d="M9 21v-5h6v5" />
        <path d="M9 11h1.5M13.5 11H15M9 14h1.5M13.5 14H15" strokeLinecap="round" />
      </g>
    ),
  },
  admin: {
    label: "Admin",
    sub: "Acesso restrito",
    cor: "#FFD23F",
    desenho: (cor) => (
      <g fill="none" stroke={cor} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" />
        <path d="M12 1v3M12 20v3M4.2 4.2l2.2 2.2M17.6 17.6l2.2 2.2M1 12h3M20 12h3M4.2 19.8l2.2-2.2M17.6 6.4l2.2-2.2" />
      </g>
    ),
  },
};

export default function LogoProduto({ produto = "home", size = 28, compact = false }) {
  const cfg = PRODUTO_CONFIG[produto] || PRODUTO_CONFIG.home;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{
        width: size, height: size, borderRadius: 8,
        background: `${cfg.cor}18`, border: `1px solid ${cfg.cor}44`,
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0,
      }}>
        <svg width={size - 8} height={size - 8} viewBox="0 0 24 24">
          {cfg.desenho(cfg.cor)}
        </svg>
      </div>
      {!compact && (
        <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.1 }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: "#EEEEE8", letterSpacing: -0.4 }}>
            {cfg.label}
          </span>
          {cfg.sub && (
            <span style={{ fontSize: 10, color: cfg.cor, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: 1, marginTop: 2, fontWeight: 600 }}>
              {cfg.sub}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export function produtoCor(produto) {
  return (PRODUTO_CONFIG[produto] || PRODUTO_CONFIG.home).cor;
}
