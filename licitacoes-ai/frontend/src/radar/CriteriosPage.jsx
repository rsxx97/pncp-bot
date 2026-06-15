import { useEffect, useState } from "react";
import { radarApi } from "./api";

// ── Cores de alerta (paridade eLicita) ─────────────────────────────────
const NIVEIS = [
  { k: "leve",     label: "Leve",     cor: "#06B6D4" },
  { k: "moderado", label: "Moderado", cor: "#22C55E" },
  { k: "grave",    label: "Grave",    cor: "#F59E0B" },
  { k: "urgente",  label: "Urgente",  cor: "#DC2626" },
];

// ── Grupos "Tipo de Comunicado" (paridade eLicita) → mapeia tipos internos ─
const GRUPOS = [
  {
    key: "avisos",
    label: "Avisos",
    descricao: "Sessão aberta/retomada, mudança de fase, republicação, adjudicação, homologação",
    tipos: ["SESSAO_ABERTA","SESSAO_RETOMADA","MUDANCA_FASE","REPUBLICACAO","ADIAMENTO","CANCELAMENTO","ADJUDICADO","HOMOLOGADO","FRACASSADO","DESERTO"],
  },
  {
    key: "chat",
    label: "Chat",
    descricao: "Mensagens do pregoeiro e contrapropostas",
    tipos: ["MENSAGEM_PREGOEIRO","CONTRAPROPOSTA"],
  },
  {
    key: "item",
    label: "Item / Lances",
    descricao: "Novo lance, você foi superado ou está na frente",
    tipos: ["NOVO_LANCE","USUARIO_SUPERADO","USUARIO_NA_FRENTE"],
  },
  {
    key: "habilitacao",
    label: "Habilitação / Documentos",
    descricao: "Convocação de documentação, pedido de diligência, habilitado/inabilitado",
    tipos: ["CONVOCACAO_PROPOSTA","CONVOCACAO_DOCUMENTACAO","PEDIDO_DILIGENCIA","HABILITADO","INABILITADO"],
  },
  {
    key: "recursos",
    label: "Recursos",
    descricao: "Recurso aberto e julgado",
    tipos: ["RECURSO_ABERTO","RECURSO_JULGADO"],
  },
  {
    key: "suspensao",
    label: "Suspensão Administrativa",
    descricao: "Sessão suspensa",
    tipos: ["SESSAO_SUSPENSA"],
  },
];

// ── Canais (UI) ↔ canais backend ───────────────────────────────────────
const CANAIS = [
  { k: "in_app",   label: "Pop-up", icon: "🖥" },
  { k: "email",    label: "Email",  icon: "✉" },
  { k: "web_push", label: "Mobile", icon: "📱" },
  { k: "sonoro",   label: "Sonoro", icon: "🔔", localOnly: true },
];

const SONORO_KEY = "radar_sonoro_por_grupo";
const carregarSonoro = () => { try { return JSON.parse(localStorage.getItem(SONORO_KEY) || "{}"); } catch { return {}; } };
const salvarSonoro = (obj) => { try { localStorage.setItem(SONORO_KEY, JSON.stringify(obj)); } catch {} };

export default function CriteriosPage() {
  const [config, setConfig] = useState(null);
  const [sonoros, setSonoros] = useState(carregarSonoro);
  const [subtab, setSubtab] = useState("comunicados");
  const [msg, setMsg] = useState("");
  const [erro, setErro] = useState("");
  const [testando, setTestando] = useState(null);
  const [salvandoLinha, setSalvandoLinha] = useState(null);

  useEffect(() => { (async () => setConfig(await radarApi.listarAlertas()))(); }, []);

  const grupoEstaAtivo = (grupo, canal) => {
    if (canal === "sonoro") return !!sonoros[grupo.key];
    if (!config || !grupo.tipos.length) return false;
    return grupo.tipos.every(t => config.matriz[t]?.[canal]?.ativo);
  };

  const grupoParcial = (grupo, canal) => {
    if (canal === "sonoro" || !config) return false;
    const ativos = grupo.tipos.filter(t => config.matriz[t]?.[canal]?.ativo).length;
    return ativos > 0 && ativos < grupo.tipos.length;
  };

  const toggleGrupo = async (grupo, canal, novoValor) => {
    setMsg(""); setErro("");
    if (canal === "sonoro") {
      const novo = { ...sonoros, [grupo.key]: novoValor };
      setSonoros(novo);
      salvarSonoro(novo);
      return;
    }
    setSalvandoLinha(`${grupo.key}-${canal}`);
    try {
      for (const tipo of grupo.tipos) {
        const regras = config.matriz[tipo]?.[canal]?.regras || {};
        await radarApi.salvarAlerta({ tipo_evento: tipo, canal, ativo: novoValor, regras });
      }
      // Atualizar local
      const novoConfig = JSON.parse(JSON.stringify(config));
      for (const tipo of grupo.tipos) {
        if (!novoConfig.matriz[tipo]) novoConfig.matriz[tipo] = {};
        if (!novoConfig.matriz[tipo][canal]) novoConfig.matriz[tipo][canal] = { ativo: false, regras: {} };
        novoConfig.matriz[tipo][canal].ativo = novoValor;
      }
      setConfig(novoConfig);
      setMsg(`${grupo.label} · ${CANAIS.find(c => c.k === canal).label}: ${novoValor ? "ativado" : "desativado"}`);
      setTimeout(() => setMsg(""), 2500);
    } catch (e) {
      setErro(e.message || "Falha ao salvar");
    }
    setSalvandoLinha(null);
  };

  const testar = async (canal) => {
    setTestando(canal); setMsg(""); setErro("");
    try {
      const destino = canal === "telegram" ? { tenant_id: "auto" } : {};
      const r = await radarApi.testarCanal({ canal, destino });
      if (r.status === "enviado" || r.status === "ok") setMsg(`${canal}: ✓ teste enviado`);
      else setErro(`${canal}: ${r.erro || r.status}`);
    } catch (e) { setErro(`${canal}: ${e.message}`); }
    setTestando(null);
  };

  if (!config) return <div style={{ color: "#98968E", padding: 20 }}>Carregando…</div>;

  return (
    <div style={{ color: "#EEEEE8" }}>
      {/* Header com título + legenda de cores */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: 8 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Critérios de Monitoramento</h2>
          <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
            <span style={{ fontSize: 10, fontFamily: "monospace", color: "#98968E", textTransform: "uppercase", letterSpacing: 0.6 }}>
              Cores de alerta:
            </span>
            {NIVEIS.map(n => (
              <span key={n.k} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11 }}>
                <span style={{ display: "inline-block", width: 14, height: 14, background: n.cor, borderRadius: 3 }} />
                <span style={{ color: "#D5D4CE" }}>{n.label}</span>
              </span>
            ))}
          </div>
        </div>
        <p style={{ fontSize: 12, color: "#98968E", margin: 0 }}>
          Por tipo de comunicado, escolha por quais canais quer ser notificado.
          <b style={{ color: "#D5D4CE" }}> Sonoro</b> é configuração local do navegador (não vai pro servidor).
        </p>
      </div>

      {/* Sub-tabs Palavra-chave / Comunicados (paridade eLicita) */}
      <div style={{ display: "flex", gap: 0, borderBottom: "1px solid #2A2A32", marginBottom: 14 }}>
        {[{ k: "palavra", l: "1. Palavra-chave" }, { k: "comunicados", l: "2. Comunicados" }].map(t => (
          <button key={t.k} onClick={() => setSubtab(t.k)}
            style={{
              padding: "10px 18px", fontSize: 11, background: "transparent", border: 0,
              borderBottom: subtab === t.k ? "2px solid #BEFF3A" : "2px solid transparent",
              color: subtab === t.k ? "#EEEEE8" : "#5A5854",
              cursor: "pointer", fontWeight: 600, fontFamily: "monospace",
              textTransform: "uppercase", letterSpacing: 0.8, marginBottom: -1,
            }}>
            {t.l}
          </button>
        ))}
      </div>

      {msg && <div style={{ background: "#16A34A22", border: "1px solid #16A34A66", color: "#34D399", padding: "8px 12px", borderRadius: 6, fontSize: 12, marginBottom: 10 }}>{msg}</div>}
      {erro && <div style={{ background: "#DC262622", border: "1px solid #DC262666", color: "#F87171", padding: "8px 12px", borderRadius: 6, fontSize: 12, marginBottom: 10 }}>{erro}</div>}

      {subtab === "palavra" && (
        <div style={{ background: "#111114", border: "1px dashed #2A2A32", padding: 24, borderRadius: 10, textAlign: "center", color: "#5A5854" }}>
          <div style={{ fontSize: 13, marginBottom: 8 }}>Palavras-chave por nível de criticidade</div>
          <div style={{ fontSize: 11, color: "#5A5854" }}>
            (Em construção — usar por enquanto a tab <b>2. Comunicados</b>)
          </div>
        </div>
      )}

      {subtab === "comunicados" && (
        <div style={{ background: "#0F0F12", border: "1px solid #2A2A32", borderRadius: 10, overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "#18181C", borderBottom: "1px solid #2A2A32" }}>
                  <th style={th}>Tipo de Comunicado</th>
                  {CANAIS.map(c => (
                    <th key={c.k} style={{ ...th, textAlign: "center", width: 120 }}>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                        <span style={{ fontSize: 15 }}>{c.icon}</span>
                        <span>{c.label}</span>
                        {!c.localOnly && (
                          <button onClick={() => testar(c.k)} disabled={testando === c.k}
                            style={{ fontSize: 9, padding: "2px 6px", background: "transparent", color: "#5A9EF7", border: "1px solid #2A2A32", borderRadius: 3, cursor: "pointer", fontFamily: "monospace", fontWeight: 600 }}>
                            {testando === c.k ? "…" : "TESTAR"}
                          </button>
                        )}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {GRUPOS.map(grupo => (
                  <tr key={grupo.key} style={{ borderBottom: "1px solid #1F1F25" }}>
                    <td style={{ padding: "14px 14px", verticalAlign: "top" }}>
                      <div style={{ fontSize: 13, color: "#EEEEE8", fontWeight: 600, marginBottom: 2 }}>{grupo.label}</div>
                      <div style={{ fontSize: 11, color: "#5A5854", maxWidth: 380 }}>{grupo.descricao}</div>
                    </td>
                    {CANAIS.map(c => {
                      const ativo = grupoEstaAtivo(grupo, c.k);
                      const parcial = grupoParcial(grupo, c.k);
                      const carregando = salvandoLinha === `${grupo.key}-${c.k}`;
                      return (
                        <td key={c.k} style={{ textAlign: "center", padding: "8px 6px" }}>
                          <SwitchPill ativo={ativo} parcial={parcial} loading={carregando}
                            onClick={() => toggleGrupo(grupo, c.k, !ativo)} />
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

const th = {
  textAlign: "left", padding: "12px 14px", fontFamily: "monospace", fontSize: 10,
  color: "#98968E", fontWeight: 700, letterSpacing: 0.6, textTransform: "uppercase",
};

function SwitchPill({ ativo, parcial, loading, onClick }) {
  return (
    <button onClick={onClick} disabled={loading}
      style={{
        width: 38, height: 22, borderRadius: 999, border: 0,
        background: ativo ? "#BEFF3A" : parcial ? "#F59E0B" : "#2A2A32",
        cursor: loading ? "wait" : "pointer", position: "relative",
        transition: "background 0.18s",
      }}>
      <span style={{
        position: "absolute", top: 2,
        left: ativo ? 18 : 2,
        width: 18, height: 18, borderRadius: "50%",
        background: ativo ? "#1A1A18" : "#EEEEE8",
        transition: "left 0.18s",
      }} />
    </button>
  );
}
