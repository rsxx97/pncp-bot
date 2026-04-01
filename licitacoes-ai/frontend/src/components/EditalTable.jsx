import { api } from "../api";

const D = {
  bg: "#09090B", s1: "#111114", s2: "#18181C", s3: "#222228",
  b1: "#2A2A32", b2: "#3A3A44",
  t1: "#EEEEE8", t2: "#98968E", t3: "#5A5854",
  ac: "#BEFF3A", rd: "#FF4D4D", am: "#FFB038", tl: "#2EDDA8", bl: "#5A9EF7", pr: "#A78BFA",
};
const mono = "'JetBrains Mono', monospace";

function formatBRL(v) {
  if (v == null || v === 0) return "N/I";
  if (v >= 1e6) return `R$ ${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `R$ ${(v / 1e3).toFixed(0)}K`;
  return `R$ ${v.toFixed(0)}`;
}

function formatDateTime(d) {
  if (!d) return "—";
  try {
    const dt = new Date(d);
    const date = `${String(dt.getDate()).padStart(2, '0')}/${String(dt.getMonth() + 1).padStart(2, '0')}`;
    const h = dt.getHours(), m = dt.getMinutes();
    if (h === 0 && m === 0) return date;
    return `${date} ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  } catch { return d; }
}

function diasRestantes(dataEnc) {
  if (!dataEnc) return null;
  try {
    return Math.ceil((new Date(dataEnc) - new Date()) / 86400000);
  } catch { return null; }
}

function ScoreBadge({ score }) {
  if (score == null) return <span style={{ fontFamily: mono, fontSize: 11, color: D.t3 }}>—</span>;
  const color = score >= 80 ? D.ac : score >= 60 ? D.am : D.rd;
  const bg = score >= 80 ? `${D.ac}1a` : score >= 60 ? `${D.am}1a` : `${D.rd}1a`;
  return <span style={{ fontFamily: mono, fontSize: 11, fontWeight: 600, color, background: bg, padding: "2px 6px", borderRadius: 4 }}>{score}</span>;
}

function StatusBadge({ status }) {
  const map = {
    novo: { bg: `${D.bl}1a`, color: D.bl, label: "Novo" },
    classificado: { bg: `${D.bl}1a`, color: D.bl, label: "Novo" },
    analisando: { bg: `${D.pr}1a`, color: D.pr, label: "Analisando" },
    analisado: { bg: `${D.tl}1a`, color: D.tl, label: "Analisado" },
    go: { bg: `${D.tl}1a`, color: D.tl, label: "Go" },
    go_com_ressalvas: { bg: `${D.tl}1a`, color: D.tl, label: "Go*" },
    nogo: { bg: `${D.rd}1a`, color: D.rd, label: "No Go" },
    precificando: { bg: `${D.am}1a`, color: D.am, label: "Precificando" },
    precificado: { bg: `${D.am}1a`, color: D.am, label: "Precificado" },
    competitivo_pronto: { bg: `${D.ac}1a`, color: D.ac, label: "Pronto" },
    erro_analise: { bg: `${D.rd}1a`, color: D.rd, label: "Erro" },
    erro_precificacao: { bg: `${D.rd}1a`, color: D.rd, label: "Erro" },
    arquivado: { bg: `${D.t3}1a`, color: D.t3, label: "Arquivado" },
  };
  const s = map[status] || { bg: `${D.bl}1a`, color: D.bl, label: status };
  return <span style={{ fontFamily: mono, fontSize: 10, fontWeight: 600, color: s.color, background: s.bg, padding: "2px 8px", borderRadius: 4 }}>{s.label}</span>;
}

function DiasTag({ dias }) {
  if (dias === null) return <span style={{ color: D.t3 }}>—</span>;
  let color = D.tl;
  if (dias <= 0) color = D.rd;
  else if (dias <= 3) color = D.rd;
  else if (dias <= 7) color = D.am;
  return <span style={{ fontFamily: mono, fontSize: 10, fontWeight: 600, color, background: `${color}1a`, padding: "2px 6px", borderRadius: 4 }}>{dias <= 0 ? "Enc." : `${dias}d`}</span>;
}

function EmpresaTag({ empresa }) {
  if (!empresa) return <span style={{ color: D.t3, fontSize: 10 }}>—</span>;
  const map = {
    manutec: { label: "Manutec", color: D.bl },
    blue: { label: "Blue", color: D.pr },
    miami: { label: "Miami", color: D.am },
  };
  const c = map[empresa.toLowerCase()] || { label: empresa, color: D.t2 };
  return <span style={{ fontFamily: mono, fontSize: 10, fontWeight: 600, color: c.color, background: `${c.color}1a`, padding: "2px 6px", borderRadius: 4 }}>{c.label}</span>;
}

function Btn({ children, primary, onClick }) {
  return (
    <button onClick={onClick} style={{
      fontFamily: mono, fontSize: 10, padding: "4px 10px", borderRadius: 6, cursor: "pointer", fontWeight: 600, border: "none",
      background: primary ? D.s3 : "transparent",
      color: primary ? D.t1 : D.t2,
      transition: "background 0.15s",
    }}
    onMouseEnter={e => e.currentTarget.style.background = D.b2}
    onMouseLeave={e => e.currentTarget.style.background = primary ? D.s3 : "transparent"}>
      {children}
    </button>
  );
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
    return (
      <div style={{ padding: 60, textAlign: "center", color: D.t3 }}>
        <div style={{ fontSize: 28, marginBottom: 8 }}>📋</div>
        <div style={{ fontSize: 14, fontWeight: 600, color: D.t2, marginBottom: 4 }}>Pipeline vazio</div>
        <div style={{ fontSize: 12, color: D.t3 }}>Adicione editais pela aba Oportunidades</div>
      </div>
    );
  }

  return (
    <div style={{ overflowX: "auto", borderRadius: 12, border: `1px solid ${D.b1}`, background: D.s1 }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, minWidth: 800 }}>
        <thead>
          <tr style={{ borderBottom: `1px solid ${D.b1}` }}>
            {["Score", "Orgão", "Objeto", "Valor", "Abertura", "Prazo", "Empresa", "Status", "Ações"].map(h => (
              <th key={h} style={{ textAlign: "left", padding: "10px 10px", fontFamily: mono, color: D.t3, fontWeight: 500, fontSize: 10, letterSpacing: 1.5, textTransform: "uppercase" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {editais.map(ed => {
            const status = ed.status || "novo";
            const dias = diasRestantes(ed.data_encerramento || ed.data_abertura);
            return (
              <tr key={ed.pncp_id} onClick={() => onSelect(ed.pncp_id)}
                style={{ borderBottom: `1px solid rgba(255,255,255,0.03)`, cursor: "pointer", transition: "background 0.1s" }}
                onMouseEnter={ev => ev.currentTarget.style.background = D.s2}
                onMouseLeave={ev => ev.currentTarget.style.background = "transparent"}>
                <td style={{ padding: "10px 10px" }}><ScoreBadge score={ed.score_relevancia} /></td>
                <td style={{ padding: "10px 10px", maxWidth: 130 }}>
                  <div style={{ fontWeight: 600, fontSize: 12, color: D.t1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{(ed.orgao_nome || "").substring(0, 20)}</div>
                  <div style={{ fontSize: 10, color: D.t3 }}>{ed.uf}{ed.municipio ? ` · ${ed.municipio}` : ""}</div>
                </td>
                <td style={{ padding: "10px 10px", maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: D.t2, fontSize: 11 }}>
                  {(ed.objeto || "").substring(0, 65)}
                </td>
                <td style={{ padding: "10px 10px", fontFamily: mono, fontWeight: 600, color: D.t1, whiteSpace: "nowrap", fontSize: 12 }}>{formatBRL(ed.valor_estimado)}</td>
                <td style={{ padding: "10px 10px", fontFamily: mono, fontSize: 11, color: D.t2, whiteSpace: "nowrap" }}>{formatDateTime(ed.data_abertura)}</td>
                <td style={{ padding: "10px 10px" }}><DiasTag dias={dias} /></td>
                <td style={{ padding: "10px 10px" }}><EmpresaTag empresa={ed.empresa_sugerida} /></td>
                <td style={{ padding: "10px 10px" }}><StatusBadge status={status} /></td>
                <td style={{ padding: "10px 6px" }}>
                  <div style={{ display: "flex", gap: 4 }} onClick={ev => ev.stopPropagation()}>
                    {(status === "novo" || status === "classificado" || status === "erro_analise") && (
                      <><Btn primary onClick={e => handleAction(e, "analisar", ed.pncp_id)}>Analisar</Btn>
                      <Btn onClick={e => handleAction(e, "arquivar", ed.pncp_id)}>Ignorar</Btn></>
                    )}
                    {(status === "analisado" || status?.startsWith("go") || status === "erro_precificacao") && (
                      <Btn primary onClick={e => handleAction(e, "planilha", ed.pncp_id)}>Planilha</Btn>
                    )}
                    {status === "precificado" && (
                      <><Btn primary onClick={e => { e.stopPropagation(); window.open(`/api/editais/${ed.pncp_id}/planilha/download`); }}>Baixar XLSX</Btn>
                      <Btn onClick={e => handleAction(e, "competitivo", ed.pncp_id)}>Dossie</Btn></>
                    )}
                    {status === "competitivo_pronto" && (
                      <><Btn primary onClick={() => onSelect(ed.pncp_id)}>Ver</Btn>
                      <Btn onClick={e => { e.stopPropagation(); window.open(`/api/editais/${ed.pncp_id}/planilha/download`); }}>XLSX</Btn></>
                    )}
                    {(status === "analisando" || status === "precificando") && (
                      <span style={{ fontFamily: mono, fontSize: 10, color: D.pr, fontStyle: "italic" }}>Processando...</span>
                    )}
                    {status === "nogo" && (
                      <Btn onClick={() => onSelect(ed.pncp_id)}>Ver motivo</Btn>
                    )}
                    <Btn onClick={async (e) => {
                      e.stopPropagation();
                      if (confirm(`Excluir edital de ${ed.orgao_nome}?`)) {
                        await fetch(`/api/editais/${ed.pncp_id}/excluir`, { method: "DELETE" });
                        onRefresh?.();
                      }
                    }}>✕</Btn>
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
