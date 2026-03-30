import { useState, useEffect, useRef } from "react";

const C = {
  bg: "#09090B", s1: "#111114", s2: "#18181C", s3: "#222228",
  b1: "#2A2A32", b2: "#3A3A44",
  t1: "#EEEEE8", t2: "#98968E", t3: "#5A5854",
  ac: "#BEFF3A", ac2: "#9AD62E",
  rd: "#FF4D4D", am: "#FFB038", tl: "#2EDDA8", bl: "#5A9EF7", pr: "#A78BFA",
};

const mono = "'JetBrains Mono', monospace";
const sans = "'Instrument Sans', 'DM Sans', sans-serif";

/* ── Animated Counter ── */
function AnimNum({ value, prefix = "", suffix = "", decimals = 0, style }) {
  const ref = useRef(null);
  const [display, setDisplay] = useState("0");
  useEffect(() => {
    const target = typeof value === "number" ? value : parseFloat(value) || 0;
    let start = null;
    const dur = 1200;
    function step(ts) {
      if (!start) start = ts;
      const p = Math.min((ts - start) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      const v = eased * target;
      if (decimals > 0) setDisplay(v.toFixed(decimals));
      else setDisplay(Math.round(v).toLocaleString("pt-BR"));
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }, [value, decimals]);
  return <span ref={ref} style={{ fontFamily: sans, fontWeight: 700, letterSpacing: -1.2, ...style }}>{prefix}{display}{suffix}</span>;
}

/* ── Sparkline ── */
function Sparkline({ data, color = C.bl, height = 24 }) {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data, 1);
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height }}>
      {data.map((v, i) => (
        <div key={i} style={{
          width: 4, borderRadius: 2,
          height: Math.max(2, (v / max) * height),
          background: color,
          opacity: i === data.length - 1 ? 1 : 0.4,
        }} />
      ))}
    </div>
  );
}

/* ── Metric Card ── */
function MetricCard({ label, value, prefix, suffix, sub, sparkData, sparkColor, decimals, delay = 0 }) {
  return (
    <div style={{
      background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 14, padding: "18px 20px",
      animation: `fadeUp 0.5s ease both`, animationDelay: `${delay}ms`,
      position: "relative", overflow: "hidden", cursor: "default",
      transition: "border-color 0.2s, transform 0.2s",
    }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = C.b2; e.currentTarget.style.transform = "translateY(-2px)"; }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = C.b1; e.currentTarget.style.transform = "translateY(0)"; }}>
      <div style={{ fontFamily: mono, fontSize: 9.5, textTransform: "uppercase", letterSpacing: 1.5, color: C.t3, marginBottom: 8 }}>{label}</div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <AnimNum value={value} prefix={prefix || ""} suffix={suffix || ""} decimals={decimals || 0} style={{ fontSize: 28, color: C.t1 }} />
          {sub && <div style={{ fontFamily: mono, fontSize: 11, color: C.t2, marginTop: 4 }}>{sub}</div>}
        </div>
        <Sparkline data={sparkData} color={sparkColor || C.bl} />
      </div>
    </div>
  );
}

/* ── Funnel ── */
function FunnelChart({ data }) {
  if (!data) return null;
  const steps = [
    { key: "monitorados", label: "Monitorados", color: C.bl },
    { key: "score_60_plus", label: "Score 60+", color: C.tl },
    { key: "analisados", label: "Analisados", color: C.pr },
    { key: "go", label: "Go", color: C.ac },
    { key: "planilha_pronta", label: "Planilha", color: C.am },
    { key: "participou", label: "Participou", color: C.ac2 },
    { key: "venceu", label: "Venceu", color: C.ac },
  ];
  const max = Math.max(...steps.map(s => data[s.key] || 0), 1);

  return (
    <div style={{ background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 14, padding: 20 }}>
      <div style={{ fontFamily: mono, fontSize: 9.5, textTransform: "uppercase", letterSpacing: 1.5, color: C.t3, marginBottom: 16 }}>Funil de conversão</div>
      {steps.map((s, i) => {
        const v = data[s.key] || 0;
        const pct = (v / max) * 100;
        return (
          <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <div style={{ fontFamily: mono, fontSize: 11, color: C.t2, width: 80, textAlign: "right" }}>{s.label}</div>
            <div style={{ flex: 1, height: 18, background: C.s2, borderRadius: 4, overflow: "hidden" }}>
              <div style={{
                height: "100%", borderRadius: 4,
                background: `linear-gradient(90deg, ${s.color}, ${s.color}66)`,
                width: `${pct}%`,
                animation: `growW 1s cubic-bezier(0.22,1,0.36,1) both`,
                animationDelay: `${i * 100}ms`,
              }} />
            </div>
            <div style={{ fontFamily: mono, fontSize: 12, color: C.t1, width: 36, fontWeight: 600 }}>{v}</div>
          </div>
        );
      })}
      {data.monitorados > 0 && (
        <div style={{ fontFamily: mono, fontSize: 10, color: C.t3, marginTop: 8, textAlign: "right" }}>
          taxa total: {((data.venceu || 0) / data.monitorados * 100).toFixed(1)}% · go→venceu: {data.go > 0 ? ((data.venceu || 0) / data.go * 100).toFixed(0) : 0}%
        </div>
      )}
    </div>
  );
}

/* ── Alerts ── */
function AlertsPanel({ alerts }) {
  if (!alerts || alerts.length === 0) return (
    <div style={{ background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 14, padding: 20 }}>
      <div style={{ fontFamily: mono, fontSize: 9.5, textTransform: "uppercase", letterSpacing: 1.5, color: C.t3, marginBottom: 16 }}>Alertas</div>
      <div style={{ fontFamily: mono, fontSize: 12, color: C.t3 }}>Nenhum edital no pipeline</div>
    </div>
  );
  const dotColor = { critico: C.rd, atencao: C.am, ok: C.t3 };
  const urgSem = alerts.filter(a => a.urgencia === "critico" && !a.tem_planilha).length;

  return (
    <div style={{ background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 14, padding: 20 }}>
      <div style={{ fontFamily: mono, fontSize: 9.5, textTransform: "uppercase", letterSpacing: 1.5, color: C.t3, marginBottom: 16 }}>Alertas</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 200, overflowY: "auto" }}>
        {alerts.slice(0, 8).map((a, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: dotColor[a.urgencia], flexShrink: 0,
              animation: a.urgencia === "critico" ? "livePulse 2s infinite" : "none" }} />
            <div style={{ flex: 1, fontSize: 12, color: C.t1, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {a.orgao_nome}
            </div>
            <div style={{
              fontFamily: mono, fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 8,
              background: a.urgencia === "critico" ? `${C.rd}1a` : a.urgencia === "atencao" ? `${C.am}1a` : `${C.bl}1a`,
              color: a.urgencia === "critico" ? C.rd : a.urgencia === "atencao" ? C.am : C.bl,
            }}>
              {a.horas_restantes < 24 ? `${Math.round(a.horas_restantes)}h` : `${Math.round(a.horas_restantes / 24)}d`}
            </div>
          </div>
        ))}
      </div>
      {urgSem > 0 && (
        <div style={{ fontFamily: mono, fontSize: 10, color: C.am, marginTop: 10, display: "flex", alignItems: "center", gap: 4 }}>
          ⚠ {urgSem} em 48h sem planilha
        </div>
      )}
    </div>
  );
}

/* ── Volume by Status ── */
function VolumeChart({ data }) {
  if (!data) return null;
  const statuses = [
    { key: "competitivo_pronto", label: "Pronto", color: C.ac },
    { key: "precificado", label: "Precificado", color: C.ac2 },
    { key: "go_com_ressalvas", label: "Go*", color: C.tl },
    { key: "analisado", label: "Analisado", color: C.pr },
    { key: "novo", label: "Novo", color: C.bl },
  ];
  const max = Math.max(...statuses.map(s => data[s.key] || 0), 1);

  const fmtV = v => {
    if (!v) return "R$ 0";
    if (v >= 1e6) return `R$ ${(v / 1e6).toFixed(1)}M`;
    if (v >= 1e3) return `R$ ${(v / 1e3).toFixed(0)}K`;
    return `R$ ${v.toFixed(0)}`;
  };

  return (
    <div style={{ background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 14, padding: 20 }}>
      <div style={{ fontFamily: mono, fontSize: 9.5, textTransform: "uppercase", letterSpacing: 1.5, color: C.t3, marginBottom: 16 }}>Volume por status</div>
      {statuses.map((s, i) => {
        const v = data[s.key] || 0;
        if (v === 0) return null;
        return (
          <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <div style={{ fontFamily: mono, fontSize: 11, color: C.t2, width: 65, textAlign: "right" }}>{s.label}</div>
            <div style={{ flex: 1, height: 14, background: C.s2, borderRadius: 3, overflow: "hidden" }}>
              <div style={{
                height: "100%", borderRadius: 3,
                background: `linear-gradient(90deg, ${s.color}, ${s.color}44)`,
                width: `${(v / max) * 100}%`,
              }} />
            </div>
            <div style={{ fontFamily: mono, fontSize: 11, color: C.t1, width: 70, fontWeight: 500 }}>{fmtV(v)}</div>
          </div>
        );
      })}
      <div style={{ fontFamily: mono, fontSize: 10, color: C.t3, marginTop: 10, display: "flex", justifyContent: "space-between" }}>
        <span>pipeline: {fmtV(data.total)}</span>
        <span>ticket: {fmtV(data.ticket_medio)}</span>
      </div>
    </div>
  );
}

/* ── Calendar ── */
function CalendarView({ data, month }) {
  if (!data) return null;
  const [y, m] = (month || new Date().toISOString().slice(0, 7)).split("-").map(Number);
  const firstDay = new Date(y, m - 1, 1).getDay();
  const daysInMonth = new Date(y, m, 0).getDate();
  const today = new Date().toISOString().slice(0, 10);
  const dayMap = {};
  (data || []).forEach(d => { dayMap[d.date] = d.editais; });
  const mNames = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

  const cells = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  return (
    <div style={{ background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 14, padding: 20 }}>
      <div style={{ fontFamily: mono, fontSize: 9.5, textTransform: "uppercase", letterSpacing: 1.5, color: C.t3, marginBottom: 12 }}>
        Calendário {mNames[m]}/{y}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7,1fr)", gap: 3, textAlign: "center" }}>
        {["D", "S", "T", "Q", "Q", "S", "S"].map((d, i) => (
          <div key={i} style={{ fontFamily: mono, fontSize: 9, color: C.t3, padding: "2px 0" }}>{d}</div>
        ))}
        {cells.map((d, i) => {
          if (d === null) return <div key={`e${i}`} />;
          const dateStr = `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
          const eds = dayMap[dateStr];
          const isToday = dateStr === today;
          const hasUrgent = eds?.some(e => e.urgente);
          return (
            <div key={i} style={{
              fontFamily: mono, fontSize: 11, padding: "4px 2px", borderRadius: 6,
              color: eds ? C.t1 : C.t3,
              background: isToday ? `${C.ac}22` : eds ? (hasUrgent ? `${C.rd}15` : `${C.bl}15`) : "transparent",
              fontWeight: eds ? 700 : 400,
              cursor: eds ? "pointer" : "default",
              transition: "transform 0.15s",
              position: "relative",
            }}
            onMouseEnter={e => eds && (e.currentTarget.style.transform = "scale(1.1)")}
            onMouseLeave={e => e.currentTarget.style.transform = "scale(1)"}>
              {d}
              {eds && <div style={{ width: 4, height: 4, borderRadius: "50%", background: hasUrgent ? C.rd : C.bl, margin: "2px auto 0" }} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Competitor Ranking ── */
function CompetitorRanking({ data }) {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data.map(d => d.score_agressividade), 1);
  const nivelColor = { alta: C.rd, media: C.am, baixa: C.tl };

  return (
    <div style={{ background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 14, padding: 20 }}>
      <div style={{ fontFamily: mono, fontSize: 9.5, textTransform: "uppercase", letterSpacing: 1.5, color: C.t3, marginBottom: 16 }}>Ranking agressividade</div>
      {data.slice(0, 5).map((c, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <div style={{ fontFamily: mono, fontSize: 11, color: C.t3, width: 14 }}>{i + 1}</div>
          <div style={{ fontSize: 12, color: C.t1, width: 100, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.nome}</div>
          <div style={{ flex: 1, height: 8, background: C.s2, borderRadius: 4, overflow: "hidden" }}>
            <div style={{
              height: "100%", borderRadius: 4,
              background: `linear-gradient(90deg, ${nivelColor[c.nivel]}, ${nivelColor[c.nivel]}44)`,
              width: `${(c.score_agressividade / max) * 100}%`,
            }} />
          </div>
          <div style={{ fontFamily: mono, fontSize: 11, color: nivelColor[c.nivel], fontWeight: 600, width: 30 }}>{c.score_agressividade}</div>
        </div>
      ))}
    </div>
  );
}

/* ── Heatmap ── */
function DiscountHeatmap({ data }) {
  if (!data || !data.segmentos || data.segmentos.length === 0) return null;
  const maxV = Math.max(...data.valores.flat().filter(v => v != null), 1);

  return (
    <div style={{ background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 14, padding: 20 }}>
      <div style={{ fontFamily: mono, fontSize: 9.5, textTransform: "uppercase", letterSpacing: 1.5, color: C.t3, marginBottom: 12 }}>Heatmap descontos</div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <thead>
            <tr>
              <th style={{ fontFamily: mono, fontSize: 9, color: C.t3, padding: 4, textAlign: "left" }}></th>
              {data.concorrentes.map((c, i) => (
                <th key={i} style={{ fontFamily: mono, fontSize: 9, color: C.t3, padding: 4, textAlign: "center", maxWidth: 50, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {c.split(" ")[0].slice(0, 6)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.segmentos.map((s, si) => (
              <tr key={si}>
                <td style={{ fontFamily: mono, fontSize: 10, color: C.t2, padding: 4 }}>{s}</td>
                {data.valores.map((row, ci) => {
                  const v = row[si];
                  if (v == null) return <td key={ci} style={{ padding: 4, textAlign: "center" }}><span style={{ color: C.t3, fontSize: 10 }}>—</span></td>;
                  const intensity = v / maxV;
                  const bg = `rgba(255, ${Math.round(176 - intensity * 130)}, ${Math.round(56 - intensity * 56)}, ${0.15 + intensity * 0.3})`;
                  return (
                    <td key={ci} style={{ padding: 2, textAlign: "center" }}>
                      <div style={{
                        fontFamily: mono, fontSize: 11, fontWeight: 600, padding: "4px 6px", borderRadius: 6,
                        background: bg, color: intensity > 0.6 ? C.rd : C.am,
                        transition: "transform 0.15s", cursor: "default",
                      }}
                      onMouseEnter={e => e.currentTarget.style.transform = "scale(1.12)"}
                      onMouseLeave={e => e.currentTarget.style.transform = "scale(1)"}>
                        {v}%
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── MAIN KPI DASHBOARD ── */
export default function KPIDashboard({ period, onPeriodChange }) {
  const [metrics, setMetrics] = useState(null);
  const [funnel, setFunnel] = useState(null);
  const [volume, setVolume] = useState(null);
  const [alerts, setAlerts] = useState(null);
  const [ranking, setRanking] = useState(null);
  const [heatmap, setHeatmap] = useState(null);
  const [calendar, setCalendar] = useState(null);
  const [sparkEditais, setSparkEditais] = useState([]);
  const [sparkPipeline, setSparkPipeline] = useState([]);
  const [apiError, setApiError] = useState(false);

  const load = () => {
    const p = period || "90d";
    setApiError(false);
    fetch(`/api/dashboard/metrics?period=${p}`).then(r => { if (!r.ok) throw r; return r.json(); }).then(setMetrics).catch(() => setApiError(true));
    fetch(`/api/dashboard/funnel?period=${p}`).then(r => r.json()).then(setFunnel).catch(() => {});
    fetch(`/api/dashboard/volume-by-status?period=${p}`).then(r => r.json()).then(setVolume).catch(() => {});
    fetch("/api/dashboard/alerts").then(r => r.json()).then(setAlerts).catch(() => {});
    fetch("/api/dashboard/competitors-ranking").then(r => r.json()).then(setRanking).catch(() => {});
    fetch("/api/dashboard/heatmap").then(r => r.json()).then(setHeatmap).catch(() => {});
    fetch("/api/dashboard/calendar").then(r => r.json()).then(setCalendar).catch(() => {});
    fetch("/api/dashboard/sparkline/editais?days=14").then(r => r.json()).then(setSparkEditais).catch(() => {});
    fetch("/api/dashboard/sparkline/pipeline_valor?days=14").then(r => r.json()).then(setSparkPipeline).catch(() => {});
  };

  useEffect(load, [period]);
  useEffect(() => { const iv = setInterval(load, 60000); return () => clearInterval(iv); }, [period]);

  const fmtV = v => {
    if (!v) return "R$ 0";
    if (v >= 1e6) return `R$ ${(v / 1e6).toFixed(1)}M`;
    if (v >= 1e3) return `R$ ${(v / 1e3).toFixed(0)}K`;
    return `R$ ${Math.round(v)}`;
  };

  return (
    <div>
      {/* CSS Animations */}
      <style>{`
        @keyframes fadeUp { from { opacity:0; transform:translateY(12px) } to { opacity:1; transform:translateY(0) } }
        @keyframes growW { from { width: 0 } to { width: 100% } }
        @keyframes livePulse { 0%,100% { box-shadow: 0 0 0 0 rgba(190,255,58,0.4) } 50% { box-shadow: 0 0 0 6px rgba(190,255,58,0) } }
      `}</style>

      {/* API Error Banner */}
      {apiError && (
        <div style={{
          background: `${C.rd}15`, border: `1px solid ${C.rd}33`, borderRadius: 10,
          padding: "12px 16px", marginBottom: 16, display: "flex", alignItems: "center", gap: 10,
        }}>
          <div style={{ fontSize: 18 }}>⚠</div>
          <div>
            <div style={{ fontFamily: mono, fontSize: 12, fontWeight: 600, color: C.rd }}>API indisponível</div>
            <div style={{ fontFamily: mono, fontSize: 11, color: C.t3 }}>
              Verifique se o backend está rodando (python run.py dashboard). Tentando reconectar a cada 60s.
            </div>
          </div>
          <button onClick={load} style={{ marginLeft: "auto", fontFamily: mono, fontSize: 10, padding: "5px 12px", borderRadius: 6, cursor: "pointer", fontWeight: 600, border: `1px solid ${C.rd}44`, background: `${C.rd}22`, color: C.rd }}>
            Tentar novamente
          </button>
        </div>
      )}

      {/* Metric Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12, marginBottom: 20 }}>
        <MetricCard label="Editais" value={metrics?.editais_total || 0} sub={`${metrics?.editais_score_60 || 0} com score 60+`}
          sparkData={sparkEditais} sparkColor={C.bl} delay={0} />
        <MetricCard label="Taxa Go" value={metrics?.taxa_go || 0} suffix="%" decimals={1} sub={`${metrics?.planilhas_prontas || 0} planilhas`}
          sparkColor={C.tl} delay={50} />
        <MetricCard label="Pipeline" value={metrics?.volume_total ? metrics.volume_total / 1e6 : 0} prefix="R$ " suffix="M" decimals={1}
          sub={`${metrics?.editais_total || 0} editais`} sparkData={sparkPipeline} sparkColor={C.pr} delay={100} />
        <MetricCard label="Custo API" value={metrics?.custo_api_hoje_usd || 0} prefix="$" decimals={2}
          sub={`${metrics?.chamadas_api_hoje || 0} chamadas`} sparkColor={C.ac} delay={150} />
        <MetricCard label="Faturamento" value={metrics?.faturamento_total ? metrics.faturamento_total / 1e6 : 0} prefix="R$ " suffix="M" decimals={1}
          sub={`${metrics?.pregoes_vencidos || 0} vencidos`} sparkColor={C.tl} delay={200} />
      </div>

      {/* Row 2: Funnel + Alerts */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        <FunnelChart data={funnel} />
        <AlertsPanel alerts={alerts} />
      </div>

      {/* Row 3: Volume + Calendar */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        <VolumeChart data={volume} />
        <CalendarView data={calendar} />
      </div>

      {/* Row 4: Ranking + Heatmap */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
        <CompetitorRanking data={ranking} />
        <DiscountHeatmap data={heatmap} />
      </div>
    </div>
  );
}
