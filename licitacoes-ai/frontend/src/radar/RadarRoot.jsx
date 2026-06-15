import { useState } from "react";
import RadarPage from "./RadarPage";
import CriteriosPage from "./CriteriosPage";
import HistoricoPage from "./HistoricoPage";
import CredenciaisPage from "./CredenciaisPage";

const TABS = [
  { key: "ao_vivo",     label: "Ao Vivo" },
  { key: "criterios",   label: "Critérios" },
  { key: "historico",   label: "Histórico" },
  { key: "credenciais", label: "Credenciais" },
];

export default function RadarRoot() {
  const [tab, setTab] = useState("ao_vivo");

  return (
    <div>
      <div style={{ display: "flex", gap: 4, marginBottom: 16, borderBottom: "1px solid #2A2A32", flexWrap: "wrap" }}>
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            style={{
              fontFamily: "'JetBrains Mono', monospace", fontSize: 11, padding: "8px 16px",
              cursor: "pointer", fontWeight: 600, border: "none",
              borderBottom: tab === t.key ? "2px solid #BEFF3A" : "2px solid transparent",
              background: "none", color: tab === t.key ? "#EEEEE8" : "#5A5854",
              marginBottom: -1, textTransform: "uppercase", letterSpacing: 1,
            }}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "ao_vivo"     && <RadarPage />}
      {tab === "criterios"   && <CriteriosPage />}
      {tab === "historico"   && <HistoricoPage />}
      {tab === "credenciais" && <CredenciaisPage />}
    </div>
  );
}
