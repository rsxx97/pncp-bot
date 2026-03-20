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

function formatDate(d) {
  if (!d) return "—";
  try {
    const dt = new Date(d);
    return `${String(dt.getDate()).padStart(2, '0')}/${String(dt.getMonth() + 1).padStart(2, '0')}`;
  } catch { return d; }
}

export default function EditalTable({ editais, onSelect, onRefresh }) {
  const handleAction = async (e, action, pncpId) => {
    e.stopPropagation();
    try {
      if (action === "analisar") await api.analisar(pncpId);
      else if (action === "planilha") await api.gerarPlanilha(pncpId);
      else if (action === "competitivo") await api.competitivo(pncpId);
      else if (action === "arquivar") await api.arquivar(pncpId);
      onRefresh?.();
    } catch (err) { console.error(err); }
  };

  if (!editais || editais.length === 0) {
    return <div style={{ padding: 40, textAlign: "center", color: "#AEAEA8" }}>Nenhum edital encontrado.</div>;
  }

  return (
    <div style={{ overflowX: "auto", borderRadius: 12, border: "1px solid #EDEDEA" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, minWidth: 700 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #EDEDEA" }}>
            {["Score", "Orgao", "Objeto", "Valor est.", "Abertura", "Status", "Acoes"].map(h => (
              <th key={h} style={{ textAlign: "left", padding: "12px 14px", color: "#AEAEA8", fontWeight: 500, fontSize: 12, letterSpacing: 0.3 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {editais.map(ed => {
            const status = ed.status || "novo";
            const orgao = (ed.orgao_nome || "").substring(0, 20);
            const objeto = (ed.objeto || "").substring(0, 60);
            return (
              <tr key={ed.pncp_id} onClick={() => onSelect(ed.pncp_id)}
                style={{ borderBottom: "1px solid #F5F5F2", cursor: "pointer", transition: "background 0.1s" }}
                onMouseEnter={ev => ev.currentTarget.style.background = "#FAFAF8"}
                onMouseLeave={ev => ev.currentTarget.style.background = "transparent"}>
                <td style={{ padding: "12px 14px" }}><ScoreBadge score={ed.score_relevancia} /></td>
                <td style={{ padding: "12px 14px", fontWeight: 600, whiteSpace: "nowrap" }}>{orgao}</td>
                <td style={{ padding: "12px 14px", maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#5A5A56" }}>{objeto}</td>
                <td style={{ padding: "12px 14px", fontWeight: 500, whiteSpace: "nowrap" }}>{formatBRL(ed.valor_estimado)}</td>
                <td style={{ padding: "12px 14px", color: "#8A8A85", whiteSpace: "nowrap" }}>{formatDate(ed.data_abertura)}</td>
                <td style={{ padding: "12px 14px" }}><StatusBadge status={status} /></td>
                <td style={{ padding: "12px 8px" }}>
                  <div style={{ display: "flex", gap: 4 }} onClick={ev => ev.stopPropagation()}>
                    {(status === "novo" || status === "classificado") && (
                      <><ActionBtn primary onClick={e => handleAction(e, "analisar", ed.pncp_id)}>Analisar</ActionBtn>
                      <ActionBtn onClick={e => handleAction(e, "arquivar", ed.pncp_id)}>Ignorar</ActionBtn></>
                    )}
                    {(status === "analisado" || status === "go" || status === "go_com_ressalvas") && (
                      <ActionBtn primary onClick={e => handleAction(e, "planilha", ed.pncp_id)}>Gerar planilha</ActionBtn>
                    )}
                    {status === "precificado" && (
                      <ActionBtn primary onClick={e => handleAction(e, "competitivo", ed.pncp_id)}>Dossie</ActionBtn>
                    )}
                    {status === "competitivo_pronto" && (
                      <><ActionBtn primary onClick={() => onSelect(ed.pncp_id)}>Dossie</ActionBtn>
                      <ActionBtn onClick={e => { e.stopPropagation(); window.open(`/api/editais/${ed.pncp_id}/planilha/download`); }}>Planilha</ActionBtn></>
                    )}
                    {(status === "analisando" || status === "precificando") && (
                      <ActionBtn>Status</ActionBtn>
                    )}
                    {status === "nogo" && (
                      <ActionBtn onClick={() => onSelect(ed.pncp_id)}>Ver motivo</ActionBtn>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
