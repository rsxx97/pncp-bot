import { useState, useEffect, useMemo } from "react";

const C = {
  bg: "#09090B", s1: "#111114", s2: "#18181C", s3: "#222228",
  b1: "#2A2A32", b2: "#3A3A44",
  t1: "#EEEEE8", t2: "#98968E", t3: "#5A5854",
  ac: "#BEFF3A", rd: "#FF4D4D", am: "#FFB038", tl: "#2EDDA8", bl: "#5A9EF7", pr: "#A78BFA",
};
const mono = "'JetBrains Mono', monospace";

const fmt = v => !v ? "—" : new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v);

function Card({ children, style = {} }) {
  return <div style={{ background: C.s2, border: `1px solid ${C.b1}`, borderRadius: 10, padding: 16, ...style }}>{children}</div>;
}

function Field({ label, value, onChange, placeholder = "" }) {
  return (
    <div>
      <label style={{ fontSize: 9, color: C.t3, textTransform: "uppercase", letterSpacing: 0.5, display: "block", marginBottom: 4 }}>{label}</label>
      <input value={value || ""} onChange={e => onChange(e.target.value)} placeholder={placeholder}
        style={{ width: "100%", padding: "6px 10px", boxSizing: "border-box",
          background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 6,
          fontSize: 11, color: C.t1, fontFamily: mono, outline: "none" }} />
    </div>
  );
}

export default function HabilitacaoPage() {
  const [empresas, setEmpresas] = useState([]);
  const [empresaSelecionada, setEmpresaSelecionada] = useState(null);
  const [tiposDisponiveis, setTiposDisponiveis] = useState([]);
  const [editais, setEditais] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busca, setBusca] = useState("");
  const [gerando, setGerando] = useState({});
  const [pacotes, setPacotes] = useState({});
  const [editandoEmpresa, setEditandoEmpresa] = useState(false);
  const [mensagem, setMensagem] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch("/api/habilitacao/empresas").then(r => r.json()),
      fetch("/api/habilitacao/tipos").then(r => r.json()),
      fetch("/api/editais?per_page=500&sort=-valor_estimado").then(r => r.json()),
    ]).then(([emp, tip, ed]) => {
      setEmpresas(emp);
      setTiposDisponiveis(tip);
      if (emp.length) setEmpresaSelecionada(emp[0]);
      setEditais((ed.items || []).filter(e => e.fonte !== "extension" && e.status !== "pregao_ext" && e.status !== "arquivado"));
      setLoading(false);
    });
  }, []);

  const filtrados = useMemo(() => {
    if (!busca.trim()) return editais;
    const s = busca.toLowerCase();
    return editais.filter(e =>
      (e.orgao_nome || "").toLowerCase().includes(s) ||
      (e.objeto || "").toLowerCase().includes(s) ||
      (e.pncp_id || "").toLowerCase().includes(s)
    );
  }, [editais, busca]);

  const gerar = async (pncp_id) => {
    setGerando(g => ({ ...g, [pncp_id]: true }));
    try {
      const r = await fetch(`/api/habilitacao/edital/${pncp_id}/gerar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ empresa_key: empresaSelecionada?.key || "manutec" }),
      });
      const d = await r.json();
      if (d.ok) {
        setPacotes(p => ({ ...p, [pncp_id]: d.download_url }));
      }
    } catch (e) { console.error(e); }
    setGerando(g => ({ ...g, [pncp_id]: false }));
  };

  const gerarTodos = async () => {
    for (const ed of filtrados.slice(0, 50)) {
      await gerar(ed.pncp_id);
    }
  };

  const salvarEmpresa = async () => {
    try {
      const r = await fetch(`/api/habilitacao/empresas/${empresaSelecionada.key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(empresaSelecionada),
      });
      if (r.ok) {
        setMensagem("Empresa atualizada com sucesso");
        setTimeout(() => setMensagem(null), 3000);
        setEditandoEmpresa(false);
      }
    } catch (e) { console.error(e); }
  };

  const updateEmpresa = (path, value) => {
    setEmpresaSelecionada(e => {
      const c = JSON.parse(JSON.stringify(e));
      const keys = path.split(".");
      let o = c;
      for (let i = 0; i < keys.length - 1; i++) o = o[keys[i]] = o[keys[i]] || {};
      o[keys[keys.length - 1]] = value;
      return c;
    });
  };

  if (loading) {
    return <div style={{ color: C.t3, fontFamily: mono, fontSize: 12, padding: 40, textAlign: "center" }}>Carregando...</div>;
  }

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 13, color: C.t1, fontWeight: 700, marginBottom: 4 }}>Auto-Habilitação</div>
        <div style={{ fontSize: 11, color: C.t3 }}>
          Gera automaticamente {tiposDisponiveis.length} declarações padrão preenchidas com dados da empresa para cada edital.
        </div>
      </div>

      {/* Empresa Selector + Editar */}
      <Card style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 250 }}>
            <div style={{ fontSize: 10, color: C.t3, textTransform: "uppercase", marginBottom: 6 }}>Empresa ativa</div>
            <select value={empresaSelecionada?.key || ""} onChange={e => setEmpresaSelecionada(empresas.find(emp => emp.key === e.target.value))}
              style={{ fontFamily: mono, fontSize: 12, padding: "6px 10px", background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 6, color: C.t1, width: "100%" }}>
              {empresas.map(e => <option key={e.key} value={e.key}>{e.razao_social} ({e.cnpj})</option>)}
            </select>
            {empresaSelecionada && (
              <div style={{ fontSize: 10, color: C.t2, marginTop: 6, lineHeight: 1.6 }}>
                {empresaSelecionada.endereco?.cidade}/{empresaSelecionada.endereco?.uf} · Rep: <span style={{ color: C.t1 }}>{empresaSelecionada.representante_legal?.nome}</span>
              </div>
            )}
          </div>
          <button onClick={() => setEditandoEmpresa(!editandoEmpresa)}
            style={{ fontFamily: mono, fontSize: 10, padding: "6px 14px", borderRadius: 6, border: `1px solid ${C.b1}`, background: editandoEmpresa ? C.s3 : "transparent", color: C.t1, cursor: "pointer", fontWeight: 600 }}>
            {editandoEmpresa ? "Fechar" : "Editar Dados"}
          </button>
        </div>

        {editandoEmpresa && empresaSelecionada && (
          <div style={{ marginTop: 12, borderTop: `1px solid ${C.b1}`, paddingTop: 12, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 10 }}>
            <Field label="Razão Social" value={empresaSelecionada.razao_social} onChange={v => updateEmpresa("razao_social", v)} />
            <Field label="CNPJ" value={empresaSelecionada.cnpj} onChange={v => updateEmpresa("cnpj", v)} />
            <Field label="Nome Fantasia" value={empresaSelecionada.nome_fantasia} onChange={v => updateEmpresa("nome_fantasia", v)} />
            <Field label="Porte (ME/EPP)" value={empresaSelecionada.porte} onChange={v => updateEmpresa("porte", v)} />
            <Field label="Logradouro" value={empresaSelecionada.endereco?.logradouro} onChange={v => updateEmpresa("endereco.logradouro", v)} />
            <Field label="Número" value={empresaSelecionada.endereco?.numero} onChange={v => updateEmpresa("endereco.numero", v)} />
            <Field label="Bairro" value={empresaSelecionada.endereco?.bairro} onChange={v => updateEmpresa("endereco.bairro", v)} />
            <Field label="Cidade" value={empresaSelecionada.endereco?.cidade} onChange={v => updateEmpresa("endereco.cidade", v)} />
            <Field label="UF" value={empresaSelecionada.endereco?.uf} onChange={v => updateEmpresa("endereco.uf", v)} />
            <Field label="CEP" value={empresaSelecionada.endereco?.cep} onChange={v => updateEmpresa("endereco.cep", v)} />
            <Field label="Telefone" value={empresaSelecionada.contato?.telefone} onChange={v => updateEmpresa("contato.telefone", v)} />
            <Field label="Email" value={empresaSelecionada.contato?.email} onChange={v => updateEmpresa("contato.email", v)} />
            <Field label="Nome Representante" value={empresaSelecionada.representante_legal?.nome} onChange={v => updateEmpresa("representante_legal.nome", v)} />
            <Field label="Cargo" value={empresaSelecionada.representante_legal?.cargo} onChange={v => updateEmpresa("representante_legal.cargo", v)} />
            <Field label="RG" value={empresaSelecionada.representante_legal?.rg} onChange={v => updateEmpresa("representante_legal.rg", v)} />
            <Field label="Órgão Emissor" value={empresaSelecionada.representante_legal?.orgao_emissor} onChange={v => updateEmpresa("representante_legal.orgao_emissor", v)} />
            <Field label="CPF" value={empresaSelecionada.representante_legal?.cpf} onChange={v => updateEmpresa("representante_legal.cpf", v)} />
            <Field label="Estado Civil" value={empresaSelecionada.representante_legal?.estado_civil} onChange={v => updateEmpresa("representante_legal.estado_civil", v)} />
            <div style={{ gridColumn: "1/-1", display: "flex", justifyContent: "flex-end" }}>
              <button onClick={salvarEmpresa}
                style={{ fontFamily: mono, fontSize: 11, padding: "8px 20px", borderRadius: 6, border: "none", background: C.ac, color: C.bg, cursor: "pointer", fontWeight: 700 }}>
                Salvar
              </button>
            </div>
          </div>
        )}
        {mensagem && <div style={{ marginTop: 10, fontSize: 11, color: C.tl, fontFamily: mono }}>{mensagem}</div>}
      </Card>

      {/* Tipos de declarações */}
      <Card style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 10, color: C.t3, textTransform: "uppercase", marginBottom: 8 }}>
          Declarações geradas automaticamente ({tiposDisponiveis.length}):
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {tiposDisponiveis.map(t => (
            <span key={t.key} style={{ fontSize: 9, padding: "3px 8px", borderRadius: 4, background: C.s3, color: C.t2, fontFamily: mono }}>
              {t.ordem}. {t.nome}
            </span>
          ))}
        </div>
      </Card>

      {/* Busca + Ação em massa */}
      <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <input value={busca} onChange={e => setBusca(e.target.value)} placeholder="Buscar edital..."
          style={{ flex: 1, minWidth: 200, padding: "8px 14px", boxSizing: "border-box",
            background: C.s2, border: `1px solid ${C.b1}`, borderRadius: 8, fontSize: 12, color: C.t1, fontFamily: mono, outline: "none" }} />
        <button onClick={gerarTodos}
          style={{ fontFamily: mono, fontSize: 11, padding: "8px 16px", borderRadius: 6, border: "none", background: C.ac, color: C.bg, cursor: "pointer", fontWeight: 700 }}>
          Gerar Todos ({Math.min(filtrados.length, 50)})
        </button>
      </div>

      {/* Tabela */}
      <Card style={{ padding: 0 }}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: mono, fontSize: 11 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C.b1}` }}>
                {["Órgão / Objeto", "Valor", "UF", "Status", "Pacote"].map((h, i) => (
                  <th key={i} style={{ padding: "10px 8px", textAlign: "left", color: C.t3, fontWeight: 600, fontSize: 9, textTransform: "uppercase", letterSpacing: 0.8 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtrados.map(e => (
                <tr key={e.pncp_id} style={{ borderBottom: `1px solid ${C.b1}22` }}>
                  <td style={{ padding: "10px 8px", maxWidth: 450 }}>
                    <div style={{ color: C.t1, fontWeight: 600, fontSize: 11 }}>{e.orgao_nome || "—"}</div>
                    <div style={{ color: C.t3, fontSize: 10, marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 430 }}>
                      {e.objeto || "—"}
                    </div>
                  </td>
                  <td style={{ padding: "10px 8px", color: C.am, fontWeight: 600, whiteSpace: "nowrap" }}>{fmt(e.valor_estimado)}</td>
                  <td style={{ padding: "10px 8px", color: C.t2 }}>{e.uf || "—"}</td>
                  <td style={{ padding: "10px 8px" }}>
                    <span style={{ fontSize: 9, padding: "2px 8px", borderRadius: 4, background: C.s3, color: C.t2 }}>
                      {e.status || "—"}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px" }}>
                    {pacotes[e.pncp_id] ? (
                      <span onClick={() => window.open(pacotes[e.pncp_id])}
                        style={{ fontSize: 10, fontWeight: 700, padding: "5px 12px", borderRadius: 4, background: C.ac + "22", color: C.ac, cursor: "pointer", whiteSpace: "nowrap" }}>
                        BAIXAR ZIP
                      </span>
                    ) : (
                      <button onClick={() => gerar(e.pncp_id)} disabled={gerando[e.pncp_id]}
                        style={{ fontFamily: mono, fontSize: 10, padding: "5px 12px", borderRadius: 4,
                          border: "none", background: gerando[e.pncp_id] ? C.s3 : C.bl + "22", color: gerando[e.pncp_id] ? C.t3 : C.bl,
                          cursor: gerando[e.pncp_id] ? "wait" : "pointer", fontWeight: 600, whiteSpace: "nowrap" }}>
                        {gerando[e.pncp_id] ? "Gerando..." : "Gerar"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ padding: "8px 12px", borderTop: `1px solid ${C.b1}`, color: C.t3, fontSize: 10, fontFamily: mono }}>
          {filtrados.length} editais
        </div>
      </Card>
    </div>
  );
}
