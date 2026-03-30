import { useState, useEffect } from "react";

const REGIMES = [
  { value: "lucro_real", label: "Lucro Real" },
  { value: "lucro_presumido", label: "Lucro Presumido" },
  { value: "simples", label: "Simples Nacional" },
];

const SERVICOS_OPCOES = [
  "limpeza", "conservacao", "facilities", "mao de obra terceirizada",
  "apoio administrativo", "recepcao", "portaria", "copeiragem",
  "vigilancia patrimonial", "seguranca", "brigada de incendio",
  "manutencao predial", "eletrica", "hidraulica",
  "engenharia", "construcao", "reforma",
];

const UFS = ["AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT","PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"];

function EmpresaForm({ empresa, onSave, onCancel }) {
  const [form, setForm] = useState({
    nome: "", regime_tributario: "lucro_real", desonerada: false,
    rat_pct: 3.0, fap: 1.0, pis_efetivo_pct: 1.65, cofins_efetivo_pct: 7.6,
    servicos: [], atestados: [], uf_atuacao: ["RJ"], cnpj: "",
    ...empresa,
  });
  const [novoAtestado, setNovoAtestado] = useState("");
  const [saving, setSaving] = useState(false);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const toggleServico = (s) => {
    set("servicos", form.servicos.includes(s) ? form.servicos.filter(x => x !== s) : [...form.servicos, s]);
  };

  const toggleUf = (u) => {
    set("uf_atuacao", form.uf_atuacao.includes(u) ? form.uf_atuacao.filter(x => x !== u) : [...form.uf_atuacao, u]);
  };

  const addAtestado = () => {
    if (novoAtestado.trim()) {
      set("atestados", [...form.atestados, novoAtestado.trim()]);
      setNovoAtestado("");
    }
  };

  const handleSave = async () => {
    setSaving(true);
    await onSave(form);
    setSaving(false);
  };

  const inputStyle = { padding: "8px 12px", border: "1px solid #D1D5DB", borderRadius: 6, fontSize: 13, width: "100%", boxSizing: "border-box" };
  const labelStyle = { fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 };

  return (
    <div style={{ background: "#FFF", borderRadius: 12, padding: 20, border: "1px solid #E5E7EB" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
        <div>
          <label style={labelStyle}>Nome da empresa</label>
          <input style={inputStyle} value={form.nome} onChange={e => set("nome", e.target.value)} placeholder="Razao social" />
        </div>
        <div>
          <label style={labelStyle}>CNPJ</label>
          <input style={inputStyle} value={form.cnpj || ""} onChange={e => set("cnpj", e.target.value)} placeholder="00.000.000/0001-00" />
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 16 }}>
        <div>
          <label style={labelStyle}>Regime tributario</label>
          <select style={inputStyle} value={form.regime_tributario} onChange={e => set("regime_tributario", e.target.value)}>
            {REGIMES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Desonerada (CPRB)</label>
          <select style={inputStyle} value={form.desonerada ? "sim" : "nao"} onChange={e => set("desonerada", e.target.value === "sim")}>
            <option value="sim">Sim</option>
            <option value="nao">Nao</option>
          </select>
        </div>
        <div>
          <label style={labelStyle}>RAT base (%)</label>
          <input style={inputStyle} type="number" step="0.1" value={form.rat_pct} onChange={e => set("rat_pct", parseFloat(e.target.value) || 0)} />
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 16 }}>
        <div>
          <label style={labelStyle}>FAP</label>
          <input style={inputStyle} type="number" step="0.01" value={form.fap} onChange={e => set("fap", parseFloat(e.target.value) || 0)} />
        </div>
        <div>
          <label style={labelStyle}>PIS efetivo (%)</label>
          <input style={inputStyle} type="number" step="0.01" value={form.pis_efetivo_pct} onChange={e => set("pis_efetivo_pct", parseFloat(e.target.value) || 0)} />
        </div>
        <div>
          <label style={labelStyle}>COFINS efetivo (%)</label>
          <input style={inputStyle} type="number" step="0.01" value={form.cofins_efetivo_pct} onChange={e => set("cofins_efetivo_pct", parseFloat(e.target.value) || 0)} />
        </div>
      </div>

      {/* Servicos */}
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Servicos oferecidos</label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {SERVICOS_OPCOES.map(s => (
            <button key={s} onClick={() => toggleServico(s)}
              style={{ fontSize: 11, padding: "4px 10px", borderRadius: 12, cursor: "pointer", border: "none",
                background: form.servicos.includes(s) ? "#1A1A18" : "#F3F4F6",
                color: form.servicos.includes(s) ? "#FFF" : "#6B7280" }}>
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* UF Atuacao */}
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>UFs de atuacao</label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {UFS.map(u => (
            <button key={u} onClick={() => toggleUf(u)}
              style={{ fontSize: 11, padding: "3px 8px", borderRadius: 4, cursor: "pointer", border: "none", minWidth: 30,
                background: form.uf_atuacao.includes(u) ? "#2563EB" : "#F3F4F6",
                color: form.uf_atuacao.includes(u) ? "#FFF" : "#6B7280" }}>
              {u}
            </button>
          ))}
        </div>
      </div>

      {/* Atestados */}
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Atestados disponiveis</label>
        {form.atestados.map((a, i) => (
          <div key={i} style={{ display: "flex", gap: 6, marginBottom: 4, alignItems: "center" }}>
            <span style={{ fontSize: 12, flex: 1, color: "#374151" }}>{a}</span>
            <button onClick={() => set("atestados", form.atestados.filter((_, j) => j !== i))}
              style={{ background: "none", border: "none", color: "#DC2626", cursor: "pointer", fontSize: 14 }}>x</button>
          </div>
        ))}
        <div style={{ display: "flex", gap: 6 }}>
          <input style={{ ...inputStyle, flex: 1 }} value={novoAtestado} onChange={e => setNovoAtestado(e.target.value)}
            placeholder="Ex: limpeza predial (area minima 5.000m2)" onKeyDown={e => e.key === "Enter" && (e.preventDefault(), addAtestado())} />
          <button onClick={addAtestado} style={{ padding: "8px 14px", background: "#F3F4F6", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600 }}>+</button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        {onCancel && <button onClick={onCancel} style={{ padding: "8px 20px", background: "#F3F4F6", border: "none", borderRadius: 8, cursor: "pointer", fontSize: 13 }}>Cancelar</button>}
        <button onClick={handleSave} disabled={saving || !form.nome}
          style={{ padding: "8px 20px", background: "#1A1A18", color: "#FFF", border: "none", borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 600 }}>
          {saving ? "Salvando..." : "Salvar empresa"}
        </button>
      </div>
    </div>
  );
}

export default function Perfil({ token, tenant, onUpdate }) {
  const [empresas, setEmpresas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const loadEmpresas = async () => {
    setLoading(true);
    try {
      const resp = await fetch("/api/perfil/empresas", { headers });
      if (resp.ok) setEmpresas(await resp.json());
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  useEffect(() => { loadEmpresas(); }, []);

  const handleSave = async (form) => {
    const url = editing ? `/api/perfil/empresas/${editing.id}` : "/api/perfil/empresas";
    const method = editing ? "PUT" : "POST";
    try {
      const resp = await fetch(url, { method, headers, body: JSON.stringify(form) });
      if (resp.ok) {
        await loadEmpresas();
        setShowForm(false);
        setEditing(null);
        onUpdate?.();
      }
    } catch (e) { console.error(e); }
  };

  const handleDelete = async (id) => {
    try {
      await fetch(`/api/perfil/empresas/${id}`, { method: "DELETE", headers });
      await loadEmpresas();
    } catch (e) { console.error(e); }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, margin: "0 0 4px" }}>Minhas empresas</h2>
          <p style={{ fontSize: 13, color: "#6B7280", margin: 0 }}>Configure o perfil tributario e atestados de cada empresa</p>
        </div>
        {!showForm && (
          <button onClick={() => { setShowForm(true); setEditing(null); }}
            style={{ padding: "8px 18px", background: "#1A1A18", color: "#FFF", border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
            + Nova empresa
          </button>
        )}
      </div>

      {showForm && (
        <div style={{ marginBottom: 20 }}>
          <EmpresaForm empresa={editing} onSave={handleSave} onCancel={() => { setShowForm(false); setEditing(null); }} />
        </div>
      )}

      {loading ? <div style={{ color: "#AEAEA8" }}>Carregando...</div> : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {empresas.map(emp => (
            <div key={emp.id} style={{ background: "#FFF", borderRadius: 10, padding: 16, border: "1px solid #E5E7EB" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 600, color: "#1A1A18" }}>{emp.nome}</div>
                  <div style={{ fontSize: 12, color: "#6B7280", marginTop: 2 }}>
                    {emp.regime_tributario?.replace("_", " ")} | {emp.desonerada ? "Desonerada" : "Nao desonerada"} | RAT {emp.rat_ajustado_pct}%
                  </div>
                  <div style={{ fontSize: 11, color: "#9CA3AF", marginTop: 4 }}>
                    Servicos: {(emp.servicos || []).join(", ") || "Nenhum"}
                  </div>
                  <div style={{ fontSize: 11, color: "#9CA3AF" }}>
                    Atestados: {(emp.atestados || []).length} | UFs: {(emp.uf_atuacao || []).join(", ")}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <button onClick={() => { setEditing(emp); setShowForm(true); }}
                    style={{ padding: "4px 12px", background: "#F3F4F6", border: "none", borderRadius: 6, fontSize: 12, cursor: "pointer" }}>Editar</button>
                  <button onClick={() => handleDelete(emp.id)}
                    style={{ padding: "4px 12px", background: "#FEF2F2", border: "none", borderRadius: 6, fontSize: 12, cursor: "pointer", color: "#DC2626" }}>Remover</button>
                </div>
              </div>
            </div>
          ))}
          {empresas.length === 0 && !showForm && (
            <div style={{ textAlign: "center", padding: 40, color: "#AEAEA8" }}>
              Nenhuma empresa cadastrada. Clique em "+ Nova empresa" para comecar.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
