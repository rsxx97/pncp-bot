import { useEffect, useState } from "react";
import { radarApi } from "./api";

const COR_CRIT = { urgente: "#DC2626", alta: "#FFB038", normal: "#5A9EF7" };

export default function HistoricoPage() {
  const [eventos, setEventos] = useState([]);
  const [dias, setDias] = useState(30);
  const [tipo, setTipo] = useState("");
  const [loading, setLoading] = useState(true);

  const carregar = async () => {
    setLoading(true);
    const params = { dias, limite: 500 };
    if (tipo) params.tipo = tipo;
    setEventos(await radarApi.historico(params));
    setLoading(false);
  };

  useEffect(() => { carregar(); }, [dias, tipo]);

  return (
    <div style={{ color: "#EEEEE8" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 8 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Histórico — {eventos.length} eventos</h2>
        <div style={{ display: "flex", gap: 6 }}>
          <select value={dias} onChange={e => setDias(Number(e.target.value))}
            style={{ padding: "4px 8px", fontSize: 11, background: "#222228", color: "#EEEEE8", border: "1px solid #2A2A32", borderRadius: 4 }}>
            <option value="7">7 dias</option>
            <option value="30">30 dias</option>
            <option value="90">90 dias</option>
            <option value="365">1 ano</option>
          </select>
          <input value={tipo} onChange={e => setTipo(e.target.value)} placeholder="filtro por tipo"
            style={{ padding: "4px 10px", fontSize: 11, background: "#222228", color: "#EEEEE8", border: "1px solid #2A2A32", borderRadius: 4, fontFamily: "monospace" }} />
          <a href={radarApi.exportCsvUrl(dias, tipo)} download
            style={{ padding: "4px 12px", fontSize: 11, background: "#BEFF3A", color: "#1A1A18", border: "none", borderRadius: 4, fontWeight: 700, textDecoration: "none" }}>
            ⤓ CSV
          </a>
        </div>
      </div>

      {loading && <div style={{ color: "#5A5854", padding: 30, textAlign: "center" }}>Carregando…</div>}

      <div style={{ background: "#0F0F12", borderRadius: 8, border: "1px solid #2A2A32", overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
          <thead>
            <tr style={{ background: "#18181C" }}>
              <th style={{ padding: "10px 12px", textAlign: "left", color: "#98968E" }}>Quando</th>
              <th style={{ padding: "10px 12px", textAlign: "left", color: "#98968E" }}>Tipo</th>
              <th style={{ padding: "10px 12px", textAlign: "left", color: "#98968E" }}>Portal</th>
              <th style={{ padding: "10px 12px", textAlign: "left", color: "#98968E" }}>Pregão</th>
              <th style={{ padding: "10px 12px", textAlign: "left", color: "#98968E" }}>Título</th>
            </tr>
          </thead>
          <tbody>
            {eventos.map(e => (
              <tr key={e.id} style={{ borderBottom: "1px solid #18181C" }}>
                <td style={{ padding: "8px 12px", fontFamily: "monospace", color: "#98968E" }}>
                  {new Date(e.criado_em).toLocaleString("pt-BR")}
                </td>
                <td style={{ padding: "8px 12px", fontFamily: "monospace", fontWeight: 600, color: COR_CRIT[e.criticidade] || "#5A9EF7" }}>
                  {e.tipo}
                </td>
                <td style={{ padding: "8px 12px", fontFamily: "monospace", color: "#EEEEE8" }}>{e.portal_slug?.toUpperCase()}</td>
                <td style={{ padding: "8px 12px", fontFamily: "monospace", color: "#EEEEE8" }}>{e.pregao_numero || e.identificador}</td>
                <td style={{ padding: "8px 12px", color: "#EEEEE8" }}>{e.titulo}</td>
              </tr>
            ))}
            {!loading && eventos.length === 0 && (
              <tr><td colSpan={5} style={{ padding: 40, textAlign: "center", color: "#5A5854" }}>Sem eventos no período.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
