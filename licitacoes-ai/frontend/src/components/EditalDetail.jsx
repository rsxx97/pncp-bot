import { useState, useEffect } from "react";
import ScoreBadge from "./ScoreBadge";
import StatusBadge from "./StatusBadge";
import ActionBtn from "./ActionButton";
import { api } from "../api";

function formatBRL(v) {
  if (v == null || v === 0) return "N/I";
  if (v >= 1e6) return `R$ ${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `R$ ${(v / 1e3).toFixed(0)}K`;
  return `R$ ${v.toFixed(0)}`;
}

export default function EditalDetailPanel({ pncpId, onClose, onRefresh }) {
  const [edital, setEdital] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!pncpId) return;
    setLoading(true);
    api.getEdital(pncpId)
      .then(setEdital)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [pncpId]);

  if (!pncpId) return null;

  const handleAction = async (action) => {
    try {
      if (action === "analisar") await api.analisar(pncpId);
      else if (action === "planilha") await api.gerarPlanilha(pncpId);
      else if (action === "competitivo") await api.competitivo(pncpId);
      else if (action === "arquivar") { await api.arquivar(pncpId); onClose(); onRefresh?.(); return; }
      // Poll
      startPolling();
    } catch (e) { console.error(e); }
  };

  const startPolling = () => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      const fresh = await api.getEdital(pncpId);
      setEdital(fresh);
      if (fresh.status !== edital?.status || attempts > 60) {
        clearInterval(interval);
        onRefresh?.();
      }
    }, 5000);
  };

  const status = edital?.status || "";

  return (
    <>
      <div onClick={onClose} style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.2)", zIndex: 999 }} />
      <div style={{ position: "fixed", top: 0, right: 0, bottom: 0, width: 420, background: "#FFFFFF", boxShadow: "-4px 0 24px rgba(0,0,0,0.08)", zIndex: 1000, display: "flex", flexDirection: "column", borderLeft: "1px solid #E8E8E4" }}>
        {/* Header */}
        <div style={{ padding: "24px 24px 16px", borderBottom: "1px solid #F0F0EC", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div style={{ flex: 1 }}>
            {loading ? <div style={{ color: "#AEAEA8" }}>Carregando...</div> : (
              <>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
                  <ScoreBadge score={edital?.score_relevancia} />
                  <StatusBadge status={status} />
                </div>
                <div style={{ fontSize: 17, fontWeight: 600, color: "#1A1A18", lineHeight: 1.3 }}>{edital?.objeto}</div>
                <div style={{ fontSize: 13, color: "#8A8A85", marginTop: 6 }}>{edital?.orgao_nome} — Abertura: {edital?.data_abertura || "N/I"}</div>
              </>
            )}
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 22, cursor: "pointer", color: "#AEAEA8", padding: 4 }}>x</button>
        </div>

        {/* Body */}
        {edital && (
          <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
            {/* Stats grid */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 24 }}>
              <div style={{ background: "#F8F8F6", borderRadius: 8, padding: 14 }}>
                <div style={{ fontSize: 12, color: "#8A8A85" }}>Valor estimado</div>
                <div style={{ fontSize: 20, fontWeight: 600, color: "#1A1A18" }}>{formatBRL(edital.valor_estimado)}</div>
              </div>
              <div style={{ background: "#F8F8F6", borderRadius: 8, padding: 14 }}>
                <div style={{ fontSize: 12, color: "#8A8A85" }}>Empresa sugerida</div>
                <div style={{ fontSize: 20, fontWeight: 600, color: "#1A1A18" }}>{edital.empresa_sugerida || "—"}</div>
              </div>
              {edital.margem_percentual != null && (
                <div style={{ background: "#F8F8F6", borderRadius: 8, padding: 14 }}>
                  <div style={{ fontSize: 12, color: "#8A8A85" }}>Margem</div>
                  <div style={{ fontSize: 20, fontWeight: 600, color: "#065F46" }}>{edital.margem_percentual?.toFixed(1)}%</div>
                </div>
              )}
              {edital.lance_sugerido_min != null && (
                <div style={{ background: "#F8F8F6", borderRadius: 8, padding: 14 }}>
                  <div style={{ fontSize: 12, color: "#8A8A85" }}>Faixa de lance</div>
                  <div style={{ fontSize: 15, fontWeight: 600, color: "#1A1A18" }}>{formatBRL(edital.lance_sugerido_min)} — {formatBRL(edital.lance_sugerido_max)}</div>
                </div>
              )}
            </div>

            {/* Acoes */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#1A1A18", marginBottom: 10 }}>Acoes disponiveis</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {(status === "novo" || status === "classificado") && <ActionBtn primary onClick={() => handleAction("analisar")}>Analisar edital</ActionBtn>}
                {(status === "analisado" || status === "go" || status === "go_com_ressalvas") && <ActionBtn primary onClick={() => handleAction("planilha")}>Gerar planilha</ActionBtn>}
                {status === "precificado" && <><ActionBtn primary onClick={() => handleAction("competitivo")}>Ver dossie competitivo</ActionBtn><ActionBtn onClick={() => window.open(`/api/editais/${pncpId}/planilha/download`)}>Baixar planilha .xlsx</ActionBtn></>}
                {status === "competitivo_pronto" && <><ActionBtn primary onClick={() => handleAction("competitivo")}>Dossie</ActionBtn><ActionBtn onClick={() => window.open(`/api/editais/${pncpId}/planilha/download`)}>Planilha</ActionBtn></>}
                {edital.link_edital && <ActionBtn onClick={() => window.open(edital.link_edital)}>Ver no PNCP</ActionBtn>}
                <ActionBtn onClick={() => handleAction("arquivar")}>Arquivar</ActionBtn>
              </div>
            </div>

            {/* Recomendacao Agente 4 */}
            {status === "competitivo_pronto" && edital.analise_competitiva_json && (
              <div style={{ background: "#F0FDF9", borderRadius: 10, padding: 16, border: "1px solid #CCFBF1", marginBottom: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#134E4A", marginBottom: 8 }}>Recomendacao do Agente 4</div>
                <div style={{ fontSize: 13, color: "#115E59", lineHeight: 1.6 }}>
                  Lance sugerido: <strong>{formatBRL(edital.analise_competitiva_json?.lance_sugerido)}</strong>.
                  {edital.analise_competitiva_json?.justificativa && ` ${edital.analise_competitiva_json.justificativa}`}
                </div>
              </div>
            )}

            {/* No-Go reason */}
            {status === "nogo" && edital.motivo_nogo && (
              <div style={{ background: "#FEF2F2", borderRadius: 10, padding: 16, border: "1px solid #FEE2E2", marginBottom: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#991B1B", marginBottom: 8 }}>Motivo do No-Go</div>
                <div style={{ fontSize: 13, color: "#7F1D1D", lineHeight: 1.6 }}>{edital.motivo_nogo}</div>
              </div>
            )}

            {/* Info adicional */}
            <div style={{ fontSize: 12, color: "#AEAEA8", marginTop: 20 }}>
              <div>PNCP ID: {edital.pncp_id}</div>
              <div>UF: {edital.uf} | Municipio: {edital.municipio || "N/I"}</div>
              <div>Encerramento: {edital.data_encerramento || "N/I"}</div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
