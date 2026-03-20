export default function ScoreBadge({ score }) {
  if (score == null) return <span style={{ color: "#AEAEA8", fontSize: 13 }}>—</span>;
  const bg = score >= 80 ? "#D1FAE5" : score >= 60 ? "#FEF3C7" : "#FEE2E2";
  const color = score >= 80 ? "#065F46" : score >= 60 ? "#92400E" : "#991B1B";
  return (
    <span style={{ background: bg, color, padding: "2px 10px", borderRadius: 6, fontSize: 13, fontWeight: 600, display: "inline-block", minWidth: 32, textAlign: "center" }}>
      {score}
    </span>
  );
}
