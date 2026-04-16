import { useState, useEffect, useMemo } from "react";

const C = {
  bg: "#09090B", s1: "#111114", s2: "#18181C", s3: "#222228",
  b1: "#2A2A32", b2: "#3A3A44",
  t1: "#EEEEE8", t2: "#98968E", t3: "#5A5854",
  ac: "#BEFF3A", rd: "#FF4D4D", am: "#FFB038", tl: "#2EDDA8", bl: "#5A9EF7", pr: "#A78BFA",
};
const mono = "'JetBrains Mono', monospace";

function fmt(v) {
  if (!v || v === 0) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v);
}

function pct(v) {
  if (!v || v === 0) return "—";
  return (v * 100).toFixed(1) + "%";
}

function Card({ children, style = {} }) {
  return (
    <div style={{ background: C.s2, border: `1px solid ${C.b1}`, borderRadius: 10, padding: 16, ...style }}>
      {children}
    </div>
  );
}

function StatBox({ label, value, color = C.t1, small = false }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontFamily: mono, fontSize: small ? 14 : 18, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 9, color: C.t3, marginTop: 2, textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</div>
    </div>
  );
}

function ScoreDot({ score }) {
  const color = score >= 80 ? C.tl : score >= 60 ? C.am : score >= 40 ? C.rd : C.t3;
  return (
    <span style={{ fontFamily: mono, fontSize: 11, fontWeight: 700, color, display: "inline-flex", alignItems: "center", gap: 4 }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: color, display: "inline-block" }} />
      {score}
    </span>
  );
}

function StatusTag({ status }) {
  const map = {
    novo: { bg: C.bl + "18", color: C.bl, label: "Novo" },
    classificado: { bg: C.bl + "18", color: C.bl, label: "Classificado" },
    analisado: { bg: C.tl + "18", color: C.tl, label: "Analisado" },
    go: { bg: C.ac + "18", color: C.ac, label: "GO" },
    go_com_ressalvas: { bg: C.am + "18", color: C.am, label: "GO c/ Ressalvas" },
    precificado: { bg: C.ac + "18", color: C.ac, label: "Precificado" },
    competitivo_pronto: { bg: C.tl + "18", color: C.tl, label: "Competitivo" },
    erro_analise: { bg: C.rd + "18", color: C.rd, label: "Erro" },
  };
  const s = map[status] || { bg: C.s3, color: C.t3, label: status || "?" };
  return (
    <span style={{ fontSize: 9, fontWeight: 600, padding: "2px 8px", borderRadius: 4, background: s.bg, color: s.color, whiteSpace: "nowrap" }}>
      {s.label}
    </span>
  );
}

function EmpresaTag({ empresa }) {
  if (!empresa) return null;
  const map = {
    manutec: { bg: C.tl + "18", color: C.tl },
    miami: { bg: C.am + "18", color: C.am },
    blue: { bg: C.bl + "18", color: C.bl },
  };
  const s = map[empresa.toLowerCase()] || { bg: C.pr + "18", color: C.pr };
  return (
    <span style={{ fontSize: 9, fontWeight: 600, padding: "2px 7px", borderRadius: 4, background: s.bg, color: s.color, textTransform: "uppercase" }}>
      {empresa}
    </span>
  );
}

function diasRestantes(dataEnc) {
  if (!dataEnc) return null;
  const diff = Math.ceil((new Date(dataEnc) - new Date()) / (1000 * 60 * 60 * 24));
  if (diff < 0) return null;
  const color = diff <= 3 ? C.rd : diff <= 7 ? C.am : C.tl;
  return <span style={{ fontFamily: mono, fontSize: 10, fontWeight: 600, color }}>{diff}d</span>;
}

export default function PlanilhaPanel() {
  const [editais, setEditais] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [searchText, setSearchText] = useState("");
  const [filterEmpresa, setFilterEmpresa] = useState("todas");
  const [sortBy, setSortBy] = useState("score");
  const [gerando, setGerando] = useState(false);
  const [batchMsg, setBatchMsg] = useState(null);

  const recarregar = () => {
    fetch("/api/editais?per_page=500&sort=-score_relevancia&abertas=true&status=novo&status=classificado&status=analisado&status=go&status=go_com_ressalvas&status=go_sem_ressalvas&status=precificado&status=competitivo_pronto&status=erro_analise&status=erro_precificacao&status=precificando")
      .then(r => r.json())
      .then(data => {
        setEditais(data.items || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => { recarregar(); }, []);

  const gerarTodas = () => {
    setGerando(true);
    setBatchMsg(null);
    fetch("/api/editais/batch/gerar-planilhas", { method: "POST" })
      .then(r => r.json())
      .then(data => {
        setBatchMsg(`${data.total} planilhas sendo geradas em background (sem custo API)`);
        setGerando(false);
        // Poll para atualizar status
        const interval = setInterval(() => { recarregar(); }, 5000);
        setTimeout(() => clearInterval(interval), data.total * 8000 + 30000);
      })
      .catch(e => {
        setBatchMsg("Erro ao iniciar geração: " + e.message);
        setGerando(false);
      });
  };

  // Métricas
  const total = editais.length;
  const volumeTotal = editais.reduce((s, e) => s + (e.valor_estimado || 0), 0);
  const comPlanilha = editais.filter(e => e.planilha_path).length;
  const semPlanilha = total - comPlanilha;
  const empresaCounts = useMemo(() => {
    const c = {};
    editais.forEach(e => { const emp = (e.empresa_sugerida || "sem").toLowerCase(); c[emp] = (c[emp] || 0) + 1; });
    return c;
  }, [editais]);

  // Filtro e busca
  const filtered = useMemo(() => {
    let list = editais;
    if (filterEmpresa !== "todas") {
      list = list.filter(e => (e.empresa_sugerida || "").toLowerCase() === filterEmpresa);
    }
    if (searchText.trim()) {
      const s = searchText.toLowerCase();
      list = list.filter(e =>
        (e.orgao_nome || "").toLowerCase().includes(s) ||
        (e.objeto || "").toLowerCase().includes(s) ||
        (e.uf || "").toLowerCase().includes(s) ||
        (e.pncp_id || "").toLowerCase().includes(s)
      );
    }
    list = [...list].sort((a, b) => {
      if (sortBy === "score") return (b.score_relevancia || 0) - (a.score_relevancia || 0);
      if (sortBy === "valor") return (b.valor_estimado || 0) - (a.valor_estimado || 0);
      if (sortBy === "prazo") return (a.data_encerramento || "z").localeCompare(b.data_encerramento || "z");
      return 0;
    });
    return list;
  }, [editais, filterEmpresa, searchText, sortBy]);

  if (loading) {
    return <div style={{ color: C.t3, fontFamily: mono, fontSize: 12, padding: 40, textAlign: "center" }}>Carregando licitações abertas...</div>;
  }

  return (
    <div>
      {/* KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10, marginBottom: 16 }}>
        <Card><StatBox label="Abertas" value={total} color={C.ac} /></Card>
        <Card><StatBox label="Com Planilha" value={comPlanilha} color={C.tl} /></Card>
        <Card><StatBox label="Sem Planilha" value={semPlanilha} color={semPlanilha > 0 ? C.am : C.t3} /></Card>
        <Card><StatBox label="Volume" value={fmt(volumeTotal)} color={C.pr} small /></Card>
        <Card style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          <button
            onClick={gerarTodas}
            disabled={gerando || semPlanilha === 0}
            style={{
              fontFamily: mono, fontSize: 11, fontWeight: 700, padding: "8px 16px",
              borderRadius: 6, cursor: gerando || semPlanilha === 0 ? "not-allowed" : "pointer",
              border: "none", background: gerando ? C.s3 : C.ac, color: C.bg,
              opacity: gerando || semPlanilha === 0 ? 0.5 : 1,
              width: "100%",
            }}>
            {gerando ? "Gerando..." : `Gerar Todas (${semPlanilha})`}
          </button>
        </Card>
      </div>
      {batchMsg && (
        <div style={{ padding: "8px 14px", background: C.tl + "18", border: `1px solid ${C.tl}33`, borderRadius: 8, fontSize: 11, color: C.tl, fontFamily: mono, marginBottom: 12 }}>
          {batchMsg}
        </div>
      )}

      {/* Filtros por empresa */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", gap: 5 }}>
          {[
            { key: "todas", label: "Todas", count: total },
            { key: "manutec", label: "Manutec", count: empresaCounts.manutec || 0 },
            { key: "miami", label: "Miami", count: empresaCounts.miami || 0 },
            { key: "blue", label: "Blue", count: empresaCounts.blue || 0 },
          ].map(f => (
            <button key={f.key} onClick={() => setFilterEmpresa(f.key)}
              style={{
                fontFamily: mono, fontSize: 10, padding: "4px 10px", borderRadius: 6, cursor: "pointer", fontWeight: 600,
                border: `1px solid ${filterEmpresa === f.key ? C.b2 : C.b1}`,
                background: filterEmpresa === f.key ? C.s3 : "transparent",
                color: filterEmpresa === f.key ? C.t1 : C.t3,
              }}>
              {f.label} ({f.count})
            </button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {[
            { key: "score", label: "Score" },
            { key: "valor", label: "Valor" },
            { key: "prazo", label: "Prazo" },
          ].map(s => (
            <button key={s.key} onClick={() => setSortBy(s.key)}
              style={{
                fontFamily: mono, fontSize: 9, padding: "3px 8px", borderRadius: 4, cursor: "pointer",
                border: "none", background: sortBy === s.key ? C.s3 : "transparent",
                color: sortBy === s.key ? C.ac : C.t3, fontWeight: 600,
              }}>
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Busca */}
      <input
        placeholder="Buscar por órgão, objeto, UF, PNCP ID..."
        value={searchText}
        onChange={e => setSearchText(e.target.value)}
        style={{
          width: "100%", padding: "8px 14px", boxSizing: "border-box", outline: "none",
          background: C.s2, border: `1px solid ${C.b1}`, borderRadius: 8,
          fontSize: 12, color: C.t1, fontFamily: mono, marginBottom: 12,
        }}
      />

      {/* Tabela */}
      <Card style={{ padding: 0 }}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: mono, fontSize: 11 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C.b1}` }}>
                {["Score", "Órgão / Objeto", "Valor", "Empresa", "Prazo", "Planilha"].map((h, i) => (
                  <th key={i} style={{ padding: "10px 8px", textAlign: "left", color: C.t3, fontWeight: 600, fontSize: 9, textTransform: "uppercase", letterSpacing: 0.8 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => {
                const isSelected = selected === e.pncp_id;
                return (
                  <tr key={e.pncp_id}
                    onClick={() => setSelected(isSelected ? null : e.pncp_id)}
                    style={{
                      borderBottom: `1px solid ${C.b1}22`, cursor: "pointer",
                      background: isSelected ? C.s3 : "transparent",
                    }}
                    onMouseEnter={ev => { if (!isSelected) ev.currentTarget.style.background = C.s3 + "66"; }}
                    onMouseLeave={ev => { if (!isSelected) ev.currentTarget.style.background = "transparent"; }}
                  >
                    <td style={{ padding: "10px 8px" }}><ScoreDot score={e.score_relevancia || 0} /></td>
                    <td style={{ padding: "10px 8px", maxWidth: 420 }}>
                      <div style={{ color: C.t1, fontWeight: 600, fontSize: 11 }}>{e.orgao_nome || "—"}</div>
                      <div style={{ color: C.t3, fontSize: 10, marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 400 }}>
                        {e.objeto || "—"}
                      </div>
                    </td>
                    <td style={{ padding: "10px 8px", color: C.am, fontWeight: 600, whiteSpace: "nowrap" }}>{fmt(e.valor_estimado)}</td>
                    <td style={{ padding: "10px 8px" }}><EmpresaTag empresa={e.empresa_sugerida} /></td>
                    <td style={{ padding: "10px 8px", whiteSpace: "nowrap" }}>
                      {diasRestantes(e.data_encerramento)}
                      <span style={{ color: C.t3, fontSize: 9, marginLeft: 4 }}>
                        {e.data_encerramento ? new Date(e.data_encerramento).toLocaleDateString("pt-BR") : "—"}
                      </span>
                    </td>
                    <td style={{ padding: "10px 8px" }}>
                      {e.planilha_path ? (
                        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                          <span
                            onClick={(ev) => { ev.stopPropagation(); window.open(`/api/editais/${e.pncp_id}/planilha/download`); }}
                            title="Planilha completa (com break-even e BDI)"
                            style={{ fontSize: 10, fontWeight: 700, padding: "3px 8px", borderRadius: 4, background: C.ac + "22", color: C.ac, cursor: "pointer", whiteSpace: "nowrap" }}>
                            COMPLETA
                          </span>
                          <span
                            onClick={(ev) => { ev.stopPropagation(); window.open(`/api/editais/${e.pncp_id}/planilha/entrega`); }}
                            title="Versão para entrega ao órgão (sem break-even)"
                            style={{ fontSize: 10, fontWeight: 700, padding: "3px 8px", borderRadius: 4, background: C.bl + "22", color: C.bl, cursor: "pointer", whiteSpace: "nowrap" }}>
                            ENTREGA
                          </span>
                          <span
                            onClick={(ev) => {
                              ev.stopPropagation();
                              const teto = e.valor_estimado || 0;
                              const sugerido = teto ? (teto * 0.85).toFixed(2) : '0';
                              const val = prompt(`Valor para fechar a planilha (R$)\n\nTeto edital: R$ ${teto.toLocaleString('pt-BR')}\nSugerido (-15%): R$ ${Number(sugerido).toLocaleString('pt-BR')}`, sugerido);
                              if (!val) return;
                              const valor_alvo = parseFloat(val.replace(/\./g,'').replace(',','.'));
                              if (isNaN(valor_alvo) || valor_alvo <= 0) { alert('Valor inválido'); return; }
                              fetch(`/api/editais/${e.pncp_id}/planilha/calibrar`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ valor_alvo })
                              })
                              .then(r => r.json())
                              .then(d => {
                                alert(`✓ Calibrando para R$ ${valor_alvo.toLocaleString('pt-BR')}\nEm ~30 seg clique em COMPLETA ou ENTREGA para baixar.`);
                              })
                              .catch(err => alert('Erro: ' + err.message));
                            }}
                            title="Calibrar planilha para fechar em valor específico"
                            style={{ fontSize: 10, fontWeight: 700, padding: "3px 8px", borderRadius: 4, background: C.am + "22", color: C.am, cursor: "pointer", whiteSpace: "nowrap" }}>
                            $ CALIBRAR
                          </span>
                        </div>
                      ) : e.status === "precificando" ? (
                        <span style={{ fontSize: 9, fontWeight: 600, padding: "2px 8px", borderRadius: 4, background: C.am + "18", color: C.am, whiteSpace: "nowrap" }}>
                          Gerando...
                        </span>
                      ) : (
                        <span style={{ fontSize: 9, color: C.t3 }}>—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
              {filtered.length === 0 && (
                <tr><td colSpan={6} style={{ padding: 30, textAlign: "center", color: C.t3 }}>Nenhuma licitação aberta encontrada</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div style={{ padding: "8px 12px", borderTop: `1px solid ${C.b1}`, color: C.t3, fontSize: 10, fontFamily: mono }}>
          {filtered.length} licitações abertas · Volume: {fmt(filtered.reduce((s, e) => s + (e.valor_estimado || 0), 0))}
        </div>
      </Card>

      {/* Detalhe expandido */}
      {selected && <EditalDetalhe editais={editais} pncpId={selected} />}
    </div>
  );
}


function EditalDetalhe({ editais, pncpId }) {
  const edital = editais.find(e => e.pncp_id === pncpId);
  if (!edital) return null;

  const analise = edital.analise_json && typeof edital.analise_json === "object" ? edital.analise_json : null;
  const postos = analise?.postos || [];
  const empresas = analise?.empresas_ranking || analise?.empresas || [];

  return (
    <div style={{ marginTop: 16, display: "grid", gap: 12 }}>
      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: C.t1, marginBottom: 4 }}>{edital.orgao_nome}</div>
            <div style={{ fontSize: 11, color: C.t2, marginBottom: 8, lineHeight: 1.5 }}>{edital.objeto}</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: 10 }}>
              <span style={{ color: C.t3 }}>PNCP: <span style={{ color: C.t2 }}>{edital.pncp_id}</span></span>
              <span style={{ color: C.t3 }}>UF: <span style={{ color: C.t2 }}>{edital.uf}</span></span>
              <span style={{ color: C.t3 }}>Modalidade: <span style={{ color: C.t2 }}>{edital.modalidade || "—"}</span></span>
              {edital.data_encerramento && (
                <span style={{ color: C.t3 }}>Encerra: <span style={{ color: C.am }}>{new Date(edital.data_encerramento).toLocaleDateString("pt-BR")}</span> ({diasRestantes(edital.data_encerramento)})</span>
              )}
            </div>
          </div>
          <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
            <StatBox label="Score" value={edital.score_relevancia || 0} color={edital.score_relevancia >= 80 ? C.tl : C.am} />
            <StatBox label="Valor" value={fmt(edital.valor_estimado)} color={C.am} small />
          </div>
        </div>
        {edital.justificativa_score && (
          <div style={{ marginTop: 10, padding: 8, background: C.s3, borderRadius: 6, fontSize: 10, color: C.t2, lineHeight: 1.5 }}>
            {edital.justificativa_score}
          </div>
        )}
      </Card>

      {postos.length > 0 && (
        <Card>
          <h3 style={{ fontSize: 11, fontWeight: 700, color: C.t1, margin: "0 0 10px", textTransform: "uppercase", letterSpacing: 1 }}>
            Postos ({postos.length})
          </h3>
          <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: mono, fontSize: 11 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C.b1}` }}>
                {["Cargo", "Qtd", "Jornada", "Salário"].map((h, i) => (
                  <th key={i} style={{ padding: "6px", textAlign: "left", color: C.t3, fontSize: 9, fontWeight: 600, textTransform: "uppercase" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {postos.map((p, i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${C.b1}22` }}>
                  <td style={{ padding: "6px", color: C.t1, fontWeight: 600 }}>{p.cargo || p.funcao || p.nome || "—"}</td>
                  <td style={{ padding: "6px", color: C.bl, fontWeight: 600 }}>{p.quantidade || p.qtd || p.postos || "—"}</td>
                  <td style={{ padding: "6px", color: C.t2 }}>{p.jornada || p.carga_horaria || "—"}</td>
                  <td style={{ padding: "6px", color: C.tl }}>{p.salario || p.piso_salarial ? fmt(p.salario || p.piso_salarial) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {empresas.length > 0 && (
        <Card>
          <h3 style={{ fontSize: 11, fontWeight: 700, color: C.t1, margin: "0 0 10px", textTransform: "uppercase", letterSpacing: 1 }}>
            Empresas Sugeridas
          </h3>
          {empresas.map((emp, i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: i < empresas.length - 1 ? `1px solid ${C.b1}22` : "none" }}>
              <span style={{ color: i === 0 ? C.ac : C.t1, fontWeight: 600, fontSize: 11 }}>
                {i + 1}. {emp.nome || emp.empresa || emp}
              </span>
              {emp.motivo && <span style={{ color: C.t3, fontSize: 9 }}>{emp.motivo}</span>}
            </div>
          ))}
        </Card>
      )}

      {edital.parecer && (
        <Card style={{ borderLeft: `3px solid ${(edital.parecer || "").startsWith("go") ? C.ac : C.rd}` }}>
          <div style={{ fontSize: 10, color: C.t3, textTransform: "uppercase", marginBottom: 4 }}>Parecer</div>
          <div style={{ fontSize: 12, color: C.t1, fontWeight: 600 }}>{edital.parecer}</div>
          {edital.motivo_nogo && <div style={{ fontSize: 10, color: C.t2, marginTop: 4 }}>{edital.motivo_nogo}</div>}
        </Card>
      )}
    </div>
  );
}
