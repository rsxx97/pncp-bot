import { useState, useEffect } from "react";
import { api } from "../api";

const D = {
  bg: "#09090B", s1: "#111114", s2: "#18181C", s3: "#222228",
  b1: "#2A2A32", b2: "#3A3A44",
  t1: "#EEEEE8", t2: "#98968E", t3: "#5A5854",
  ac: "#BEFF3A", rd: "#FF4D4D", am: "#FFB038", tl: "#2EDDA8", bl: "#5A9EF7", pr: "#A78BFA",
};
const mono = "'JetBrains Mono', monospace";

const STATUS_MAP = {
  agendado: { label: "Agendado", color: D.bl, icon: "📅" },
  em_disputa: { label: "Em Disputa", color: D.am, icon: "⚡" },
  suspensa: { label: "Suspensa", color: D.rd, icon: "⏸" },
  encerrado: { label: "Encerrado", color: D.pr, icon: "🏁" },
  habilitacao: { label: "Habilitação", color: D.am, icon: "📋" },
  resultado: { label: "Resultado", color: D.tl, icon: "📊" },
  recurso: { label: "Em Recurso", color: D.rd, icon: "⚖" },
  homologado: { label: "Homologado", color: D.ac, icon: "✅" },
  contrato: { label: "Contratado", color: D.ac, icon: "📝" },
  fracassado: { label: "Fracassado", color: D.rd, icon: "❌" },
};

const RESULTADO_MAP = {
  vencedor: { label: "VENCEDOR", color: D.ac },
  perdido: { label: "Perdido", color: D.rd },
  desclassificado: { label: "Desclassificado", color: D.rd },
  inabilitado: { label: "Inabilitado", color: D.am },
};

function Badge({ label, color }) {
  return (
    <span style={{ fontFamily: mono, fontSize: 10, fontWeight: 700, color, background: `${color}1a`, padding: "3px 8px", borderRadius: 4 }}>
      {label}
    </span>
  );
}

function formatBRL(v) {
  if (v == null || v === 0) return "—";
  return `R$ ${v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// ── Formulário para registrar pregão ──
function RegistrarPregaoForm({ editais, onCreated }) {
  const [pncpId, setPncpId] = useState("");
  const [dataSessao, setDataSessao] = useState("");
  const [horaSessao, setHoraSessao] = useState("");
  const [portal, setPortal] = useState("comprasnet");
  const [linkPortal, setLinkPortal] = useState("");
  const [empresa, setEmpresa] = useState("");
  const [valorProposta, setValorProposta] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    if (!pncpId) return;
    setSaving(true);
    try {
      await fetch("/api/pregoes/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pncp_id: pncpId,
          data_sessao: dataSessao || null,
          hora_sessao: horaSessao || null,
          portal,
          link_portal: linkPortal || null,
          nossa_empresa: empresa || null,
          valor_proposta: valorProposta ? parseFloat(valorProposta) : null,
        }),
      });
      onCreated?.();
      setPncpId("");
    } catch (e) { console.error(e); }
    setSaving(false);
  };

  const inputStyle = { background: D.s2, border: `1px solid ${D.b1}`, borderRadius: 6, padding: "6px 10px", color: D.t1, fontSize: 12, fontFamily: mono, outline: "none", width: "100%" };

  return (
    <div style={{ background: D.s1, border: `1px solid ${D.b1}`, borderRadius: 12, padding: 20, marginBottom: 20 }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: D.t1, marginBottom: 12 }}>Registrar Participação em Pregão</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: 10, color: D.t3, marginBottom: 4, fontFamily: mono, textTransform: "uppercase" }}>Edital</div>
          <select value={pncpId} onChange={e => setPncpId(e.target.value)} style={inputStyle}>
            <option value="">Selecione...</option>
            {editais?.map(ed => (
              <option key={ed.pncp_id} value={ed.pncp_id}>{ed.orgao_nome?.substring(0, 30)} — {ed.objeto?.substring(0, 40)}</option>
            ))}
          </select>
        </div>
        <div>
          <div style={{ fontSize: 10, color: D.t3, marginBottom: 4, fontFamily: mono, textTransform: "uppercase" }}>Data Sessão</div>
          <input type="date" value={dataSessao} onChange={e => setDataSessao(e.target.value)} style={inputStyle} />
        </div>
        <div>
          <div style={{ fontSize: 10, color: D.t3, marginBottom: 4, fontFamily: mono, textTransform: "uppercase" }}>Hora</div>
          <input type="time" value={horaSessao} onChange={e => setHoraSessao(e.target.value)} style={inputStyle} />
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 10, marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: 10, color: D.t3, marginBottom: 4, fontFamily: mono, textTransform: "uppercase" }}>Portal</div>
          <select value={portal} onChange={e => setPortal(e.target.value)} style={inputStyle}>
            <option value="comprasnet">ComprasNet</option>
            <option value="comprasrj">ComprasRJ</option>
            <option value="comprasbr">ComprasBR</option>
            <option value="licitacoes-e">Licitações-e (BB)</option>
            <option value="outro">Outro</option>
          </select>
        </div>
        <div>
          <div style={{ fontSize: 10, color: D.t3, marginBottom: 4, fontFamily: mono, textTransform: "uppercase" }}>Link do Portal</div>
          <input value={linkPortal} onChange={e => setLinkPortal(e.target.value)} placeholder="https://..." style={inputStyle} />
        </div>
        <div>
          <div style={{ fontSize: 10, color: D.t3, marginBottom: 4, fontFamily: mono, textTransform: "uppercase" }}>Nossa Empresa</div>
          <input value={empresa} onChange={e => setEmpresa(e.target.value)} placeholder="Manutec" style={inputStyle} />
        </div>
        <div>
          <div style={{ fontSize: 10, color: D.t3, marginBottom: 4, fontFamily: mono, textTransform: "uppercase" }}>Valor Proposta (R$)</div>
          <input value={valorProposta} onChange={e => setValorProposta(e.target.value)} placeholder="0.00" style={inputStyle} />
        </div>
      </div>
      <button onClick={handleSubmit} disabled={!pncpId || saving}
        style={{ fontFamily: mono, fontSize: 12, fontWeight: 700, padding: "8px 20px", borderRadius: 8, border: "none", cursor: "pointer", background: D.ac, color: D.bg }}>
        {saving ? "Salvando..." : "Registrar Pregão"}
      </button>
    </div>
  );
}

// ── Detalhe do Pregão ──
function PregaoDetalhe({ pregaoId, onBack }) {
  const [data, setData] = useState(null);
  const [novoLance, setNovoLance] = useState({ empresa: "", valor: "", nosso: false, rodada: 1 });
  const [novaMsg, setNovaMsg] = useState("");
  const [chatRemetente, setChatRemetente] = useState("pregoeiro");
  const [novoStatus, setNovoStatus] = useState("");
  const [novaClass, setNovaClass] = useState({ posicao: "", empresa: "", valor_proposta: "", valor_lance_final: "", cnpj: "", habilitado: true });

  const carregar = async () => {
    const resp = await fetch(`/api/pregoes/${pregaoId}`);
    setData(await resp.json());
  };

  useEffect(() => { carregar(); }, [pregaoId]);

  if (!data) return <div style={{ color: D.t3, padding: 40, textAlign: "center" }}>Carregando...</div>;

  const { pregao, lances, chat, eventos, classificacao = [] } = data;

  const addClassificacao = async () => {
    if (!novaClass.posicao || !novaClass.empresa) return;
    await fetch(`/api/pregoes/${pregaoId}/classificacao`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        posicao: parseInt(novaClass.posicao),
        empresa: novaClass.empresa,
        cnpj: novaClass.cnpj || null,
        valor_proposta: novaClass.valor_proposta ? parseFloat(novaClass.valor_proposta) : null,
        valor_lance_final: novaClass.valor_lance_final ? parseFloat(novaClass.valor_lance_final) : null,
        habilitado: novaClass.habilitado,
      }),
    });
    setNovaClass({ posicao: "", empresa: "", valor_proposta: "", valor_lance_final: "", cnpj: "", habilitado: true });
    carregar();
  };

  const removeClassificacao = async (classId) => {
    await fetch(`/api/pregoes/${pregaoId}/classificacao/${classId}`, { method: "DELETE" });
    carregar();
  };
  const st = STATUS_MAP[pregao.status] || { label: pregao.status, color: D.t2 };
  const res = pregao.resultado ? RESULTADO_MAP[pregao.resultado] : null;

  const addLance = async () => {
    if (!novoLance.empresa || !novoLance.valor) return;
    await fetch(`/api/pregoes/${pregaoId}/lances`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ empresa: novoLance.empresa, valor: parseFloat(novoLance.valor), nosso: novoLance.nosso }),
    });
    setNovoLance({ empresa: "", valor: "", nosso: false });
    carregar();
  };

  const addChat = async () => {
    if (!novaMsg) return;
    await fetch(`/api/pregoes/${pregaoId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mensagem: novaMsg, remetente: chatRemetente }),
    });
    setNovaMsg("");
    carregar();
  };

  const updateStatus = async (status, extra = {}) => {
    await fetch(`/api/pregoes/${pregaoId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, ...extra }),
    });
    carregar();
  };

  const inputStyle = { background: D.s2, border: `1px solid ${D.b1}`, borderRadius: 6, padding: "6px 10px", color: D.t1, fontSize: 12, fontFamily: mono, outline: "none" };
  const btnStyle = { fontFamily: mono, fontSize: 10, padding: "5px 12px", borderRadius: 6, border: "none", cursor: "pointer", fontWeight: 600 };

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <button onClick={onBack} style={{ ...btnStyle, background: D.s3, color: D.t2, marginBottom: 8 }}>← Voltar</button>
          <div style={{ fontSize: 16, fontWeight: 700, color: D.t1 }}>{pregao.orgao_nome}</div>
          <div style={{ fontSize: 12, color: D.t2, marginTop: 2 }}>{pregao.objeto?.substring(0, 80)}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ marginBottom: 6 }}><Badge label={`${st.icon} ${st.label}`} color={st.color} /></div>
          {res && <Badge label={res.label} color={res.color} />}
        </div>
      </div>

      {/* Cards de info */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10, marginBottom: 20 }}>
        {[
          { label: "UASG", value: pregao.uasg || "—" },
          { label: "Portal", value: (pregao.edital_portal || pregao.portal || "—").toUpperCase() },
          { label: "Sessão", value: `${pregao.data_sessao || "—"} ${pregao.hora_sessao || ""}` },
          { label: "Proposta", value: formatBRL(pregao.valor_proposta) },
          { label: "Lance Final", value: formatBRL(pregao.lance_final) },
          { label: "Posição", value: pregao.posicao_final ? `${pregao.posicao_final}º de ${pregao.total_participantes || "?"}` : "—" },
          { label: "Vencedor", value: pregao.vencedor_nome || "—" },
          { label: "Valor Vencedor", value: formatBRL(pregao.vencedor_valor) },
        ].map((c, i) => (
          <div key={i} style={{ background: D.s1, border: `1px solid ${D.b1}`, borderRadius: 8, padding: "10px 12px" }}>
            <div style={{ fontFamily: mono, fontSize: 9, color: D.t3, textTransform: "uppercase", marginBottom: 4 }}>{c.label}</div>
            <div style={{ fontFamily: mono, fontSize: 13, fontWeight: 600, color: D.t1 }}>{c.value}</div>
          </div>
        ))}
      </div>

      {/* Ações de Status */}
      <div style={{ display: "flex", gap: 6, marginBottom: 20, flexWrap: "wrap" }}>
        {["agendado", "em_disputa", "suspensa", "encerrado", "habilitacao", "resultado", "recurso", "homologado", "contrato"].map(s => {
          const info = STATUS_MAP[s];
          const active = pregao.status === s;
          return (
            <button key={s} onClick={() => updateStatus(s)}
              style={{ ...btnStyle, background: active ? `${info.color}33` : D.s3, color: active ? info.color : D.t3, border: active ? `1px solid ${info.color}44` : `1px solid ${D.b1}` }}>
              {info.icon} {info.label}
            </button>
          );
        })}
      </div>

      {/* Resultado + Dados Finais */}
      <div style={{ background: D.s1, border: `1px solid ${D.b1}`, borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <div style={{ fontFamily: mono, fontSize: 12, fontWeight: 700, color: D.t1, marginBottom: 12 }}>Resultado do Pregão</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8, marginBottom: 12 }}>
          <div>
            <div style={{ fontSize: 10, color: D.t3, fontFamily: mono, textTransform: "uppercase", marginBottom: 4 }}>Nosso Lance Final</div>
            <input value={pregao.lance_final || ""} onChange={e => {
              const v = e.target.value;
              fetch(`/api/pregoes/${pregaoId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lance_final: v ? parseFloat(v) : null }) }).then(carregar);
            }} onBlur={carregar} placeholder="R$ 0.00" style={inputStyle} />
          </div>
          <div>
            <div style={{ fontSize: 10, color: D.t3, fontFamily: mono, textTransform: "uppercase", marginBottom: 4 }}>Nossa Posição</div>
            <input value={pregao.posicao_final || ""} onChange={e => {
              fetch(`/api/pregoes/${pregaoId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ posicao_final: e.target.value ? parseInt(e.target.value) : null }) }).then(carregar);
            }} placeholder="1" type="number" style={inputStyle} />
          </div>
          <div>
            <div style={{ fontSize: 10, color: D.t3, fontFamily: mono, textTransform: "uppercase", marginBottom: 4 }}>Total Participantes</div>
            <input value={pregao.total_participantes || ""} onChange={e => {
              fetch(`/api/pregoes/${pregaoId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ total_participantes: e.target.value ? parseInt(e.target.value) : null }) }).then(carregar);
            }} placeholder="5" type="number" style={inputStyle} />
          </div>
          <div>
            <div style={{ fontSize: 10, color: D.t3, fontFamily: mono, textTransform: "uppercase", marginBottom: 4 }}>Habilitação</div>
            <select value={pregao.habilitacao_status || ""} onChange={e => {
              fetch(`/api/pregoes/${pregaoId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ habilitacao_status: e.target.value || null }) }).then(carregar);
            }} style={inputStyle}>
              <option value="">—</option>
              <option value="habilitado">Habilitado</option>
              <option value="inabilitado">Inabilitado</option>
              <option value="em_analise">Em análise</option>
            </select>
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 12 }}>
          <div>
            <div style={{ fontSize: 10, color: D.t3, fontFamily: mono, textTransform: "uppercase", marginBottom: 4 }}>Empresa Vencedora</div>
            <input value={pregao.vencedor_nome || ""} onChange={e => {
              fetch(`/api/pregoes/${pregaoId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ vencedor_nome: e.target.value || null }) }).then(carregar);
            }} placeholder="Nome da empresa vencedora" style={inputStyle} />
          </div>
          <div>
            <div style={{ fontSize: 10, color: D.t3, fontFamily: mono, textTransform: "uppercase", marginBottom: 4 }}>Valor Vencedor</div>
            <input value={pregao.vencedor_valor || ""} onChange={e => {
              fetch(`/api/pregoes/${pregaoId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ vencedor_valor: e.target.value ? parseFloat(e.target.value) : null }) }).then(carregar);
            }} placeholder="R$ 0.00" style={inputStyle} />
          </div>
          <div>
            <div style={{ fontSize: 10, color: D.t3, fontFamily: mono, textTransform: "uppercase", marginBottom: 4 }}>Prazo Recursos</div>
            <input type="date" value={pregao.recursos_prazo || ""} onChange={e => {
              fetch(`/api/pregoes/${pregaoId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ recursos_prazo: e.target.value || null }) }).then(carregar);
            }} style={inputStyle} />
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 12 }}>
          <div>
            <div style={{ fontSize: 10, color: D.t3, fontFamily: mono, textTransform: "uppercase", marginBottom: 4 }}>Data Homologação</div>
            <input type="date" value={pregao.homologacao_data || ""} onChange={e => {
              fetch(`/api/pregoes/${pregaoId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ homologacao_data: e.target.value || null }) }).then(carregar);
            }} style={inputStyle} />
          </div>
          <div>
            <div style={{ fontSize: 10, color: D.t3, fontFamily: mono, textTransform: "uppercase", marginBottom: 4 }}>Nº Contrato</div>
            <input value={pregao.contrato_numero || ""} onChange={e => {
              fetch(`/api/pregoes/${pregaoId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ contrato_numero: e.target.value || null }) }).then(carregar);
            }} placeholder="CT-001/2026" style={inputStyle} />
          </div>
          <div>
            <div style={{ fontSize: 10, color: D.t3, fontFamily: mono, textTransform: "uppercase", marginBottom: 4 }}>Observações</div>
            <input value={pregao.observacoes || ""} onChange={e => {
              fetch(`/api/pregoes/${pregaoId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ observacoes: e.target.value || null }) }).then(carregar);
            }} placeholder="Notas..." style={inputStyle} />
          </div>
        </div>
        {/* Botões de Resultado */}
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{ fontFamily: mono, fontSize: 10, color: D.t3 }}>Resultado:</span>
          {["vencedor", "perdido", "desclassificado", "inabilitado"].map(r => (
            <button key={r} onClick={() => {
              const extra = r === "vencedor" ? { vencedor_nome: pregao.nossa_empresa || "Nossa empresa" } : {};
              fetch(`/api/pregoes/${pregaoId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resultado: r, ...extra }) }).then(carregar);
            }}
              style={{ ...btnStyle, background: pregao.resultado === r ? `${RESULTADO_MAP[r].color}33` : D.s3, color: pregao.resultado === r ? RESULTADO_MAP[r].color : D.t3, border: pregao.resultado === r ? `1px solid ${RESULTADO_MAP[r].color}44` : `1px solid ${D.b1}` }}>
              {RESULTADO_MAP[r].label}
            </button>
          ))}
        </div>
      </div>

      {/* Classificação Final */}
      <div style={{ background: D.s1, border: `1px solid ${D.b1}`, borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div style={{ fontFamily: mono, fontSize: 12, fontWeight: 700, color: D.t1 }}>Classificação Final ({classificacao.length} empresas)</div>
          <button onClick={async () => {
            const btn = event?.target;
            const resp = await fetch(`/api/pregoes/${pregaoId}/buscar-resultado`, { method: "POST" });
            const data = await resp.json();
            const portais = (data.portais_consultados || []).join(", ");
            const msg = data.vencedor
              ? `✅ Vencedor: ${data.vencedor}\n\nPortais consultados: ${portais}`
              : `⏳ ${data.mensagem}\n\nPortais consultados: ${portais}\n\n${(data.erros || []).map(e => `⚠ ${e}`).join("\n")}`;
            alert(msg);
            carregar();
          }} style={{ ...btnStyle, background: D.bl, color: "#FFF" }}>
            🔍 Buscar Resultado (PNCP + ComprasGov)
          </button>
        </div>
        {classificacao.length > 0 && (
          <div style={{ marginBottom: 12, overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: mono, fontSize: 11 }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${D.b1}` }}>
                  {["#", "Empresa", "CNPJ", "Proposta", "Lance Final", "Desc.", "Hab.", ""].map(h => (
                    <th key={h} style={{ textAlign: "left", padding: "6px 8px", color: D.t3, fontSize: 9, textTransform: "uppercase", fontWeight: 500 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {classificacao.map((c, i) => {
                  const isNosso = c.empresa.toLowerCase().includes(pregao.nossa_empresa?.toLowerCase() || "###");
                  const medalha = c.posicao === 1 ? "🥇" : c.posicao === 2 ? "🥈" : c.posicao === 3 ? "🥉" : `${c.posicao}º`;
                  return (
                    <tr key={c.id} style={{ borderBottom: `1px solid rgba(255,255,255,0.03)`, background: isNosso ? `${D.ac}0d` : "transparent" }}>
                      <td style={{ padding: "6px 8px", fontWeight: 700, color: c.posicao === 1 ? D.ac : D.t1 }}>{medalha}</td>
                      <td style={{ padding: "6px 8px", fontWeight: isNosso ? 700 : 400, color: isNosso ? D.ac : D.t1 }}>
                        {c.empresa} {isNosso && <span style={{ fontSize: 8, color: D.ac }}>NOSSO</span>}
                      </td>
                      <td style={{ padding: "6px 8px", color: D.t3 }}>{c.cnpj || "—"}</td>
                      <td style={{ padding: "6px 8px", color: D.t2 }}>{formatBRL(c.valor_proposta)}</td>
                      <td style={{ padding: "6px 8px", fontWeight: 600, color: D.t1 }}>{formatBRL(c.valor_lance_final)}</td>
                      <td style={{ padding: "6px 8px", color: D.am, fontSize: 10 }}>
                        {pregao.valor_estimado && c.valor_lance_final
                          ? `${((1 - c.valor_lance_final / pregao.valor_estimado) * 100).toFixed(1)}%`
                          : "—"}
                      </td>
                      <td style={{ padding: "6px 8px" }}>
                        <button onClick={async (e) => {
                          e.stopPropagation();
                          await fetch(`/api/pregoes/${pregaoId}/classificacao/${c.id}/habilitacao`, {
                            method: "PUT",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ habilitado: !c.habilitado }),
                          });
                          carregar();
                        }} style={{ cursor: "pointer", border: "none", background: c.habilitado ? `${D.tl}1a` : `${D.rd}1a`, padding: "2px 8px", borderRadius: 4 }}>
                          <span style={{ fontSize: 9, fontWeight: 600, color: c.habilitado ? D.tl : D.rd }}>
                            {c.habilitado ? "✓ HAB" : "✕ INAB"}
                          </span>
                        </button>
                      </td>
                      <td style={{ padding: "6px 4px" }}>
                        <button onClick={() => removeClassificacao(c.id)} style={{ background: "none", border: "none", color: D.rd, cursor: "pointer", fontSize: 10 }}>✕</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          <input value={novaClass.posicao} onChange={e => setNovaClass({ ...novaClass, posicao: e.target.value })} placeholder="#" type="number" style={{ ...inputStyle, width: 40 }} />
          <input value={novaClass.empresa} onChange={e => setNovaClass({ ...novaClass, empresa: e.target.value })} placeholder="Nome da empresa" style={{ ...inputStyle, flex: 2, minWidth: 140 }} />
          <input value={novaClass.cnpj} onChange={e => setNovaClass({ ...novaClass, cnpj: e.target.value })} placeholder="CNPJ" style={{ ...inputStyle, flex: 1, minWidth: 100 }} />
          <input value={novaClass.valor_proposta} onChange={e => setNovaClass({ ...novaClass, valor_proposta: e.target.value })} placeholder="Proposta R$" style={{ ...inputStyle, width: 90 }} />
          <input value={novaClass.valor_lance_final} onChange={e => setNovaClass({ ...novaClass, valor_lance_final: e.target.value })} placeholder="Lance Final R$" style={{ ...inputStyle, width: 100 }} />
          <label style={{ display: "flex", alignItems: "center", gap: 4, fontFamily: mono, fontSize: 10, color: D.t3 }}>
            <input type="checkbox" checked={novaClass.habilitado} onChange={e => setNovaClass({ ...novaClass, habilitado: e.target.checked })} /> Hab.
          </label>
          <button onClick={addClassificacao} style={{ ...btnStyle, background: D.ac, color: D.bg }}>+ Adicionar</button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Lances */}
        <div style={{ background: D.s1, border: `1px solid ${D.b1}`, borderRadius: 12, padding: 16 }}>
          <div style={{ fontFamily: mono, fontSize: 12, fontWeight: 700, color: D.t1, marginBottom: 12 }}>Lances ({lances.length})</div>
          <div style={{ maxHeight: 250, overflowY: "auto", marginBottom: 10 }}>
            {lances.map((l, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 8px", marginBottom: 2, borderRadius: 6, background: l.nosso ? `${D.ac}0d` : "transparent", borderBottom: `1px solid ${D.b1}` }}>
                <div>
                  <span style={{ fontFamily: mono, fontSize: 11, fontWeight: l.nosso ? 700 : 400, color: l.nosso ? D.ac : D.t2 }}>{l.empresa}</span>
                  {l.nosso ? <span style={{ fontSize: 9, color: D.ac, marginLeft: 6 }}>NOSSO</span> : null}
                </div>
                <div style={{ textAlign: "right" }}>
                  <span style={{ fontFamily: mono, fontSize: 12, fontWeight: 600, color: l.nosso ? D.ac : D.t1 }}>{formatBRL(l.valor)}</span>
                  <span style={{ fontFamily: mono, fontSize: 9, color: D.t3, marginLeft: 6 }}>R{l.rodada} {l.horario || ""}</span>
                </div>
              </div>
            ))}
            {lances.length === 0 && <div style={{ color: D.t3, fontSize: 11, padding: 8 }}>Registre os lances da sessão aqui</div>}
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <input value={novoLance.empresa} onChange={e => setNovoLance({ ...novoLance, empresa: e.target.value })} placeholder="Empresa" style={{ ...inputStyle, flex: 2, minWidth: 120 }} />
            <input value={novoLance.valor} onChange={e => setNovoLance({ ...novoLance, valor: e.target.value })} placeholder="Valor" style={{ ...inputStyle, flex: 1, minWidth: 80 }} />
            <input value={novoLance.rodada || 1} onChange={e => setNovoLance({ ...novoLance, rodada: parseInt(e.target.value) || 1 })} placeholder="Rd" type="number" style={{ ...inputStyle, width: 40 }} />
            <label style={{ display: "flex", alignItems: "center", gap: 4, fontFamily: mono, fontSize: 10, color: D.t3 }}>
              <input type="checkbox" checked={novoLance.nosso} onChange={e => setNovoLance({ ...novoLance, nosso: e.target.checked })} /> Nosso
            </label>
            <button onClick={addLance} style={{ ...btnStyle, background: D.ac, color: D.bg }}>+ Lance</button>
          </div>
        </div>

        {/* Chat do Pregoeiro */}
        <div style={{ background: D.s1, border: `1px solid ${D.b1}`, borderRadius: 12, padding: 16 }}>
          <div style={{ fontFamily: mono, fontSize: 12, fontWeight: 700, color: D.t1, marginBottom: 12 }}>Chat da Sessão ({chat.length})</div>
          <div style={{ maxHeight: 250, overflowY: "auto", marginBottom: 10 }}>
            {chat.map((m, i) => (
              <div key={i} style={{ padding: "6px 8px", marginBottom: 4, borderRadius: 6, background: m.remetente === "pregoeiro" ? `${D.bl}0d` : `${D.ac}0d` }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontFamily: mono, fontSize: 9, fontWeight: 600, color: m.remetente === "pregoeiro" ? D.bl : D.ac, textTransform: "uppercase" }}>{m.remetente}</span>
                  <span style={{ fontFamily: mono, fontSize: 9, color: D.t3 }}>{m.horario}</span>
                </div>
                <div style={{ fontSize: 12, color: D.t1, marginTop: 3 }}>{m.mensagem}</div>
              </div>
            ))}
            {chat.length === 0 && <div style={{ color: D.t3, fontSize: 11, padding: 8 }}>Registre mensagens do pregoeiro e comunicados</div>}
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <select value={chatRemetente || "pregoeiro"} onChange={e => setChatRemetente(e.target.value)} style={{ ...inputStyle, width: 110 }}>
              <option value="pregoeiro">Pregoeiro</option>
              <option value="nossa_empresa">Nossa empresa</option>
              <option value="sistema">Sistema</option>
              <option value="concorrente">Concorrente</option>
            </select>
            <input value={novaMsg} onChange={e => setNovaMsg(e.target.value)} placeholder="Mensagem..." style={{ ...inputStyle, flex: 1 }}
              onKeyDown={e => e.key === "Enter" && addChat()} />
            <button onClick={addChat} style={{ ...btnStyle, background: D.ac, color: D.bg }}>Enviar</button>
          </div>
        </div>
      </div>

      {/* Timeline de Eventos */}
      <div style={{ background: D.s1, border: `1px solid ${D.b1}`, borderRadius: 12, padding: 16, marginTop: 16 }}>
        <div style={{ fontFamily: mono, fontSize: 12, fontWeight: 700, color: D.t1, marginBottom: 12 }}>Timeline ({eventos.length})</div>
        {eventos.map((ev, i) => (
          <div key={i} style={{ display: "flex", gap: 10, padding: "6px 0", borderBottom: i < eventos.length - 1 ? `1px solid ${D.b1}` : "none" }}>
            <div style={{ fontFamily: mono, fontSize: 10, color: D.t3, minWidth: 60 }}>{ev.data_hora?.split("T")[0]}</div>
            <Badge label={ev.tipo} color={ev.tipo === "resultado" ? D.ac : ev.tipo === "status" ? D.bl : D.t2} />
            <div style={{ fontSize: 12, color: D.t1 }}>{ev.descricao}</div>
          </div>
        ))}
        {eventos.length === 0 && <div style={{ color: D.t3, fontSize: 11 }}>Nenhum evento</div>}
      </div>
    </div>
  );
}

// ── Componente Principal ──
export default function PregaoPanel({ editais }) {
  const [pregoes, setPregoes] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [showForm, setShowForm] = useState(false);

  const carregar = async () => {
    try {
      const [pResp, sResp] = await Promise.all([
        fetch("/api/pregoes/").then(r => r.json()),
        fetch("/api/pregoes/stats").then(r => r.json()),
      ]);
      setPregoes(pResp);
      setStats(sResp);
    } catch (e) { console.error(e); }
  };

  useEffect(() => { carregar(); }, []);

  if (selectedId) {
    return <PregaoDetalhe pregaoId={selectedId} onBack={() => { setSelectedId(null); carregar(); }} />;
  }

  return (
    <div>
      {/* Stats */}
      {stats && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 10, marginBottom: 20 }}>
          {[
            { label: "Total", value: stats.total, color: D.t1 },
            { label: "Agendados", value: stats.agendados, color: D.bl },
            { label: "Vencidos", value: stats.vencidos, color: D.ac },
            { label: "Perdidos", value: stats.perdidos, color: D.rd },
            { label: "Homologados", value: stats.homologados, color: D.tl },
            { label: "Taxa Sucesso", value: `${stats.taxa_sucesso}%`, color: D.am },
          ].map((c, i) => (
            <div key={i} style={{ background: D.s1, border: `1px solid ${D.b1}`, borderRadius: 8, padding: "10px 12px" }}>
              <div style={{ fontFamily: mono, fontSize: 9, color: D.t3, textTransform: "uppercase" }}>{c.label}</div>
              <div style={{ fontFamily: mono, fontSize: 20, fontWeight: 700, color: c.color, marginTop: 2 }}>{c.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Botão novo */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, color: D.t1, margin: 0 }}>Meus Pregões</h2>
        <button onClick={() => setShowForm(!showForm)}
          style={{ fontFamily: mono, fontSize: 11, fontWeight: 700, padding: "6px 16px", borderRadius: 8, border: "none", cursor: "pointer", background: D.ac, color: D.bg }}>
          {showForm ? "Fechar" : "+ Registrar Pregão"}
        </button>
      </div>

      {showForm && <RegistrarPregaoForm editais={editais} onCreated={() => { setShowForm(false); carregar(); }} />}

      {/* Lista */}
      {pregoes.length === 0 ? (
        <div style={{ padding: 40, textAlign: "center", color: D.t3 }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>⚡</div>
          <div style={{ fontSize: 13, color: D.t2 }}>Nenhum pregão registrado</div>
          <div style={{ fontSize: 11, color: D.t3, marginTop: 4 }}>Registre sua participação clicando no botão acima</div>
        </div>
      ) : (
        <div style={{ borderRadius: 12, border: `1px solid ${D.b1}`, background: D.s1, overflow: "hidden" }}>
          {pregoes.map((p, i) => {
            const st = STATUS_MAP[p.status] || { label: p.status, color: D.t2, icon: "📄" };
            const res = p.resultado ? RESULTADO_MAP[p.resultado] : null;
            return (
              <div key={p.id} onClick={() => setSelectedId(p.id)}
                style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", cursor: "pointer",
                  borderBottom: i < pregoes.length - 1 ? `1px solid rgba(255,255,255,0.03)` : "none", transition: "background 0.1s" }}
                onMouseEnter={e => e.currentTarget.style.background = D.s2}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: D.t1 }}>{p.orgao_nome?.substring(0, 35)}</div>
                  <div style={{ fontSize: 11, color: D.t2, marginTop: 2 }}>{p.objeto?.substring(0, 60)}</div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontFamily: mono, fontSize: 11, color: D.t2 }}>{p.data_sessao || "—"} {p.hora_sessao || ""}</div>
                    <div style={{ fontFamily: mono, fontSize: 12, fontWeight: 600, color: D.t1 }}>{formatBRL(p.lance_final || p.valor_proposta)}</div>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4, alignItems: "flex-end" }}>
                    <Badge label={`${st.icon} ${st.label}`} color={st.color} />
                    {res && <Badge label={res.label} color={res.color} />}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
