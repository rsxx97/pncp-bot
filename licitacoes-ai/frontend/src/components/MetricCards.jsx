function MetricCard({ label, value, sub }) {
  return (
    <div style={{ background: "#F8F8F6", borderRadius: 10, padding: "18px 20px", minWidth: 0 }}>
      <div style={{ fontSize: 13, color: "#8A8A85", marginBottom: 4, letterSpacing: 0.2 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 600, color: "#1A1A18", letterSpacing: -0.5 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: "#AEAEA8", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

export default function MetricCards({ metrics }) {
  if (!metrics) return null;

  const volume = metrics.volume_total >= 1e6
    ? `R$ ${(metrics.volume_total / 1e6).toFixed(1)}M`
    : `R$ ${(metrics.volume_total / 1e3).toFixed(0)}K`;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10, marginBottom: 28 }}>
      <MetricCard label="Editais hoje" value={metrics.editais_hoje} sub={`${metrics.editais_score_60} com score 60+`} />
      <MetricCard label="Score 60+" value={metrics.editais_score_60} sub={`de ${metrics.editais_hoje + metrics.editais_score_60} total`} />
      <MetricCard label="Planilhas geradas" value={metrics.planilhas_prontas} sub={`${volume} em volume`} />
      <MetricCard label="Custo API hoje" value={`$${metrics.custo_api_hoje_usd.toFixed(2)}`} sub={`${metrics.chamadas_api_hoje} chamadas`} />
    </div>
  );
}
