const STATUS_CONFIG = {
  novo: { label: "Novo", bg: "#DBEAFE", color: "#1E40AF" },
  classificado: { label: "Classificado", bg: "#DBEAFE", color: "#1E40AF" },
  analisando: { label: "Analisando", bg: "#EDE9FE", color: "#5B21B6" },
  analisado: { label: "Go", bg: "#D1FAE5", color: "#065F46" },
  go: { label: "Go", bg: "#D1FAE5", color: "#065F46" },
  go_com_ressalvas: { label: "Go*", bg: "#FEF3C7", color: "#92400E" },
  precificando: { label: "Precificando", bg: "#FEF3C7", color: "#92400E" },
  precificado: { label: "Precificado", bg: "#FEF3C7", color: "#92400E" },
  competitivo_pronto: { label: "Pronto", bg: "#CCFBF1", color: "#134E4A" },
  pronto: { label: "Pronto", bg: "#CCFBF1", color: "#134E4A" },
  nogo: { label: "No-Go", bg: "#FEE2E2", color: "#991B1B" },
  descartado: { label: "Descartado", bg: "#F3F4F6", color: "#6B7280" },
  arquivado: { label: "Arquivado", bg: "#F3F4F6", color: "#6B7280" },
  favorito: { label: "Favorito", bg: "#EDE9FE", color: "#7C3AED" },
  erro_analise: { label: "Erro", bg: "#FEE2E2", color: "#991B1B" },
  erro_precificacao: { label: "Erro", bg: "#FEE2E2", color: "#991B1B" },
};

export { STATUS_CONFIG };

export default function StatusBadge({ status }) {
  const c = STATUS_CONFIG[status] || STATUS_CONFIG.novo;
  return (
    <span style={{ background: c.bg, color: c.color, padding: "3px 10px", borderRadius: 12, fontSize: 12, fontWeight: 500, whiteSpace: "nowrap" }}>
      {c.label}
    </span>
  );
}
