import { useState, useEffect, useCallback } from "react";
import { api } from "./api";
import MetricCards from "./components/MetricCards";
import EditalTable from "./components/EditalTable";
import EditalDetailPanel from "./components/EditalDetail";
import WeeklyChart from "./components/WeeklyChart";
import ConcorrentePanel from "./components/ConcorrentePanel";

export default function App() {
  const [metrics, setMetrics] = useState(null);
  const [editais, setEditais] = useState([]);
  const [totalEditais, setTotalEditais] = useState(0);
  const [weeklyData, setWeeklyData] = useState([]);
  const [concorrentes, setConcorrentes] = useState([]);
  const [filter, setFilter] = useState("todos");
  const [selectedPncpId, setSelectedPncpId] = useState(null);
  const [now, setNow] = useState(new Date());

  const statusMap = {
    todos: [],
    novo: ["novo", "classificado"],
    go: ["analisado", "go", "go_com_ressalvas"],
    pronto: ["precificado", "competitivo_pronto"],
  };

  const loadMetrics = useCallback(async () => {
    try { setMetrics(await api.getMetrics()); } catch (e) { console.error(e); }
  }, []);

  const loadEditais = useCallback(async () => {
    try {
      const params = { per_page: 50, sort: "-score_relevancia" };
      if (filter !== "todos") params.status = statusMap[filter];
      const data = await api.getEditais(params);
      setEditais(data.items);
      setTotalEditais(data.total);
    } catch (e) { console.error(e); }
  }, [filter]);

  const loadWeekly = useCallback(async () => {
    try { setWeeklyData(await api.getWeeklyChart()); } catch (e) { console.error(e); }
  }, []);

  const loadConcorrentes = useCallback(async () => {
    try { setConcorrentes(await api.getConcorrentes()); } catch (e) { console.error(e); }
  }, []);

  const loadAll = useCallback(() => {
    loadMetrics();
    loadEditais();
    loadWeekly();
    loadConcorrentes();
  }, [loadMetrics, loadEditais, loadWeekly, loadConcorrentes]);

  useEffect(() => { loadAll(); }, [loadAll]);
  useEffect(() => { loadEditais(); }, [filter, loadEditais]);
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 60000);
    return () => clearInterval(t);
  }, []);

  const filters = [
    { key: "todos", label: "Todos", count: totalEditais },
    { key: "novo", label: "Novos", count: editais.filter(e => e.status === "novo" || e.status === "classificado").length },
    { key: "go", label: "Go", count: editais.filter(e => ["analisado", "go", "go_com_ressalvas"].includes(e.status)).length },
    { key: "pronto", label: "Prontos", count: editais.filter(e => ["precificado", "competitivo_pronto"].includes(e.status)).length },
  ];

  const ultimoScan = metrics?.ultimo_scan
    ? new Date(metrics.ultimo_scan).toLocaleString("pt-BR", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short" })
    : "—";

  return (
    <div style={{ fontFamily: "'DM Sans', -apple-system, sans-serif", color: "#1A1A18", maxWidth: 960, margin: "0 auto", padding: "0 4px" }}>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28, marginTop: 24, flexWrap: "wrap", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0, letterSpacing: -0.5 }}>Licitacoes AI</h1>
          {metrics?.monitor_ativo && (
            <span style={{ background: "#D1FAE5", color: "#065F46", fontSize: 12, fontWeight: 600, padding: "4px 12px", borderRadius: 20 }}>Monitor ativo</span>
          )}
        </div>
        <div style={{ fontSize: 13, color: "#AEAEA8" }}>Ultimo scan: {ultimoScan}</div>
      </div>

      {/* Metrics */}
      <MetricCards metrics={metrics} />

      {/* Pipeline header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Pipeline de editais</h2>
        <div style={{ display: "flex", gap: 6 }}>
          {filters.map(f => (
            <button key={f.key} onClick={() => setFilter(f.key)}
              style={{ fontSize: 12, padding: "5px 14px", borderRadius: 20, cursor: "pointer", fontWeight: 500, border: "none", transition: "all 0.15s",
                background: filter === f.key ? "#1A1A18" : "#F0F0EC", color: filter === f.key ? "#FFFFFF" : "#8A8A85" }}>
              {f.label} ({f.count})
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div style={{ marginBottom: 32 }}>
        <EditalTable editais={editais} onSelect={setSelectedPncpId} onRefresh={loadAll} />
      </div>

      {/* Bottom grid */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16, marginBottom: 24 }}>
        <div style={{ border: "1px solid #EDEDEA", borderRadius: 12, padding: "20px 24px" }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, margin: "0 0 16px", color: "#1A1A18" }}>Editais por semana</h3>
          <WeeklyChart data={weeklyData} />
        </div>
        <div style={{ border: "1px solid #EDEDEA", borderRadius: 12, padding: "20px 24px" }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, margin: "0 0 16px", color: "#1A1A18" }}>Concorrentes ativos</h3>
          <ConcorrentePanel concorrentes={concorrentes} />
        </div>
      </div>

      {/* Detail panel */}
      {selectedPncpId && (
        <EditalDetailPanel pncpId={selectedPncpId} onClose={() => setSelectedPncpId(null)} onRefresh={loadAll} />
      )}
    </div>
  );
}
