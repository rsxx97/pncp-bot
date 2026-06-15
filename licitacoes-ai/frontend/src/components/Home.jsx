import { useState, useEffect } from "react";
import KPIDashboard from "./KPIDashboard";
import { radarApi } from "../radar/api";
import { useAuth } from "../AuthContext";

const C = {
  bg: "#09090B", s1: "#111114", s2: "#18181C", s3: "#222228",
  b1: "#2A2A32", b2: "#3A3A44",
  t1: "#EEEEE8", t2: "#98968E", t3: "#5A5854",
  ac: "#BEFF3A", rd: "#FF4D4D", am: "#FFB038", tl: "#2EDDA8", bl: "#5A9EF7",
};
const mono = "'JetBrains Mono', monospace";

function navegar(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

const CRIT = {
  urgente:  { cor: "#DC2626", label: "Urgente" },
  grave:    { cor: "#F59E0B", label: "Grave" },
  moderado: { cor: "#22C55E", label: "Moderado" },
  leve:     { cor: "#06B6D4", label: "Leve" },
};

export default function Home({ period }) {
  const { tenant } = useAuth();
  const quotaRadar = Math.max(1, tenant?.plano_radar_limite || 50);
  const [radarStats, setRadarStats] = useState({ monitorados: 0, eventos30d: {}, ativos: 0 });

  useEffect(() => {
    (async () => {
      try {
        const [pregoes, historico] = await Promise.all([
          radarApi.listarPregoes(),
          radarApi.historico({ dias: 30, limite: 500 }).catch(() => []),
        ]);
        const ativos = pregoes.filter(p => p.status === "em_sessao").length;
        const por = { urgente: 0, grave: 0, moderado: 0, leve: 0 };
        for (const e of historico) {
          if (e.lido_em) continue;
          const c = (e.criticidade || "leve").toLowerCase();
          if (c in por) por[c]++;
          else por.moderado++;
        }
        setRadarStats({ monitorados: pregoes.length, eventos30d: por, ativos });
      } catch (e) { console.error("home stats:", e); }
    })();
  }, []);

  const pct = Math.round((radarStats.monitorados / quotaRadar) * 100);
  const corBarra = pct > 90 ? C.rd : pct > 75 ? C.am : C.tl;

  return (
    <div>
      <KPIDashboard period={period} />

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16, marginTop: 24 }}>
        {/* Estatísticas Radar 30d — paridade eLicita */}
        <div style={{ background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 10, padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <h3 style={{ fontSize: 12, fontWeight: 700, margin: 0, color: C.t2, letterSpacing: 0.8, textTransform: "uppercase", fontFamily: mono }}>
              Estatísticas do Radar · últimos 30 dias
            </h3>
            <button onClick={() => navegar("/radar")}
              style={{ fontSize: 10, fontFamily: mono, background: "transparent", border: `1px solid ${C.b1}`, color: C.t2, padding: "4px 10px", borderRadius: 4, cursor: "pointer", fontWeight: 600 }}>
              IR PARA RADAR →
            </button>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={statHead}>Categoria</th>
                <th style={{ ...statHead, textAlign: "right" }}>Mensagens não lidas</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(CRIT).map(([k, info]) => (
                <tr key={k} style={{ borderTop: `1px solid ${C.b1}` }}>
                  <td style={{ padding: "10px 12px", color: C.t1, fontSize: 13 }}>
                    <span style={{ display: "inline-block", width: 12, height: 12, background: info.cor, borderRadius: 3, marginRight: 10, verticalAlign: "middle" }} />
                    {info.label}
                  </td>
                  <td style={{ padding: "10px 12px", textAlign: "right", fontFamily: mono, fontSize: 13, fontWeight: 700, color: info.cor }}>
                    {radarStats.eventos30d[k] || 0}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Consumo — paridade eLicita */}
        <div style={{ background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 10, padding: 16 }}>
          <h3 style={{ fontSize: 12, fontWeight: 700, margin: "0 0 14px", color: C.t2, letterSpacing: 0.8, textTransform: "uppercase", fontFamily: mono }}>
            Consumo
          </h3>

          <div style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 11, color: C.t3, fontFamily: mono, marginBottom: 6 }}>RADAR · licitações monitoradas</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginBottom: 8 }}>
              <span style={{ fontSize: 28, fontWeight: 700, color: C.t1, letterSpacing: -1 }}>{radarStats.monitorados}</span>
              <span style={{ fontSize: 13, color: C.t3, fontFamily: mono }}>/ {quotaRadar}</span>
              <span style={{ marginLeft: "auto", fontSize: 11, fontFamily: mono, color: corBarra, fontWeight: 700 }}>{pct}%</span>
            </div>
            <div style={{ width: "100%", height: 8, background: C.s3, borderRadius: 999, overflow: "hidden" }}>
              <div style={{ width: `${Math.min(pct, 100)}%`, height: "100%", background: corBarra, borderRadius: 999, transition: "width 0.5s" }} />
            </div>
            {pct > 80 && (
              <div style={{ fontSize: 11, color: C.am, marginTop: 8, fontFamily: mono }}>
                ⚠ Cota próxima do limite — considere expandir o plano
              </div>
            )}
          </div>

          <div style={{ borderTop: `1px solid ${C.b1}`, paddingTop: 14, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <Stat label="Em sessão agora" value={radarStats.ativos} cor={C.ac} />
            <Stat label="Eventos urgentes" value={radarStats.eventos30d.urgente || 0} cor={C.rd} />
          </div>
        </div>
      </div>
    </div>
  );
}

const statHead = {
  padding: "8px 12px", textAlign: "left", fontSize: 10, fontFamily: mono,
  color: C.t3, letterSpacing: 0.8, textTransform: "uppercase", fontWeight: 600,
};

function Stat({ label, value, cor }) {
  return (
    <div>
      <div style={{ fontSize: 10, fontFamily: mono, color: C.t3, textTransform: "uppercase", letterSpacing: 0.6 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: cor || C.t1, marginTop: 2 }}>{value}</div>
    </div>
  );
}
