const COR = {
  conectado: "#16A34A",
  connecting: "#FFB038",
  desconectado: "#DC2626",
  nao_autenticado: "#6B7280",
};

const LABEL = {
  conectado: "ao vivo",
  connecting: "conectando…",
  desconectado: "reconectando…",
  nao_autenticado: "sem token",
};

export default function ConnectionIndicator({ status }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      padding: "3px 10px", borderRadius: 12, fontSize: 11,
      background: COR[status] + "22", color: COR[status], fontWeight: 600,
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      <span style={{
        width: 7, height: 7, borderRadius: "50%",
        background: COR[status],
        animation: status === "conectado" ? "pulse 2s infinite" : "none",
      }} />
      {LABEL[status]}
    </span>
  );
}
