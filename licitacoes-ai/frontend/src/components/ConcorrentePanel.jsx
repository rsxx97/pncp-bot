const AGR_CONFIG = {
  alta: { label: "Alta", bg: "#FEE2E2", color: "#991B1B" },
  media: { label: "Media", bg: "#FEF3C7", color: "#92400E" },
  baixa: { label: "Baixa", bg: "#D1FAE5", color: "#065F46" },
};

export default function ConcorrentePanel({ concorrentes }) {
  if (!concorrentes || concorrentes.length === 0) {
    return <div style={{ color: "#AEAEA8", fontSize: 13, padding: "20px 0" }}>Nenhum concorrente cadastrado.</div>;
  }

  return (
    <div>
      {concorrentes.map(c => {
        const nome = c.nome_fantasia || c.razao_social || c.cnpj;
        const agr = AGR_CONFIG[c.agressividade] || AGR_CONFIG.media;
        return (
          <div key={c.cnpj} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderBottom: "1px solid #F5F5F2" }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13, color: "#1A1A18" }}>{nome}</div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 3 }}>
                <span style={{ fontSize: 12, color: "#AEAEA8" }}>{c.lances_mes || 0} lances/mes</span>
                <span style={{ fontSize: 11, padding: "1px 8px", borderRadius: 10, fontWeight: 500, background: agr.bg, color: agr.color }}>
                  {agr.label}
                </span>
              </div>
            </div>
            <div style={{ fontSize: 13, color: "#8A8A85", fontWeight: 500 }}>desc. {c.desconto_medio || 0}%</div>
          </div>
        );
      })}
    </div>
  );
}
