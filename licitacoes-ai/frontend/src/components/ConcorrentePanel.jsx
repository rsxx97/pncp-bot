import { useState, useEffect } from "react";

const C = {
  bg: "#09090B", s1: "#111114", s2: "#18181C", s3: "#222228",
  b1: "#2A2A32", b2: "#3A3A44",
  t1: "#EEEEE8", t2: "#98968E", t3: "#5A5854",
  ac: "#BEFF3A", rd: "#FF4D4D", am: "#FFB038", tl: "#2EDDA8", bl: "#5A9EF7", pr: "#A78BFA",
};
const mono = "'JetBrains Mono', monospace";

const AGR = {
  alta: { label: "Alta", bg: `${C.rd}1a`, color: C.rd },
  media: { label: "Média", bg: `${C.am}1a`, color: C.am },
  baixa: { label: "Baixa", bg: `${C.tl}1a`, color: C.tl },
  desconhecida: { label: "?", bg: `${C.t3}1a`, color: C.t3 },
};

function Badge({ text, bg, color }) {
  return <span style={{ fontFamily: mono, fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 4, background: bg, color, whiteSpace: "nowrap" }}>{text}</span>;
}

function BuscarPncpModal({ onClose, onImport }) {
  const [termo, setTermo] = useState("");
  const [uf, setUf] = useState("RJ");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [error, setError] = useState("");

  const buscar = async () => {
    if (termo.length < 3) return;
    setLoading(true); setError(""); setResults([]);
    try {
      const resp = await fetch(`/api/concorrentes/buscar-pncp?termo=${encodeURIComponent(termo)}&uf=${uf}`);
      const data = await resp.json();
      setResults(data.items || []);
      if (data.nota) setError(data.nota);
    } catch (e) { setError("Erro na busca"); }
    setLoading(false);
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center" }} onClick={onClose}>
      <div style={{ background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 16, padding: 24, width: 520, maxHeight: "80vh", overflowY: "auto" }} onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: C.t1 }}>Buscar concorrente no PNCP</div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: C.t3, fontSize: 18, cursor: "pointer" }}>✕</button>
        </div>

        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <input value={termo} onChange={e => setTermo(e.target.value)} placeholder="Nome da empresa (ex: Nova Rio)"
            onKeyDown={e => e.key === "Enter" && buscar()}
            style={{ flex: 1, padding: "8px 12px", background: C.s2, border: `1px solid ${C.b1}`, borderRadius: 8, color: C.t1, fontSize: 13, fontFamily: mono, outline: "none" }} />
          <select value={uf} onChange={e => setUf(e.target.value)}
            style={{ padding: "8px 10px", background: C.s2, border: `1px solid ${C.b1}`, borderRadius: 8, color: C.t1, fontSize: 12, fontFamily: mono }}>
            {["RJ","SP","MG","ES","CE","AC","DF","BA","PR","RS","SC","PE","GO","PA","MA","AM"].map(u => <option key={u}>{u}</option>)}
          </select>
          <button onClick={buscar} disabled={loading}
            style={{ padding: "8px 16px", background: C.ac, color: "#000", border: "none", borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: "pointer", opacity: loading ? 0.5 : 1 }}>
            {loading ? "..." : "Buscar"}
          </button>
        </div>

        {error && <div style={{ fontFamily: mono, fontSize: 11, color: C.am, marginBottom: 8 }}>{error}</div>}

        <div style={{ fontSize: 11, color: C.t3, marginBottom: 8 }}>
          {results.length > 0 ? `${results.length} encontrados — clique para importar` : "Busca por nome nos resultados de licitações recentes"}
        </div>

        {results.map((r, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", borderBottom: `1px solid ${C.b1}`, cursor: "pointer", transition: "background 0.15s" }}
            onMouseEnter={e => e.currentTarget.style.background = C.s2}
            onMouseLeave={e => e.currentTarget.style.background = "transparent"}
            onClick={() => onImport(r)}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: C.t1 }}>{r.razao_social}</div>
              <div style={{ fontFamily: mono, fontSize: 11, color: C.t3 }}>CNPJ: {r.cnpj} · {r.participacoes} participações</div>
            </div>
            <button style={{ padding: "4px 12px", background: C.s3, border: `1px solid ${C.b2}`, borderRadius: 6, color: C.ac, fontSize: 11, fontWeight: 600, cursor: "pointer" }}>
              + Importar
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function AddManualModal({ onClose, onSave }) {
  const [cnpj, setCnpj] = useState("");
  const [nome, setNome] = useState("");
  const [fantasia, setFantasia] = useState("");
  const [notas, setNotas] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!cnpj.trim()) return;
    setSaving(true);
    await onSave({ cnpj, razao_social: nome, nome_fantasia: fantasia, segmentos: [], notas });
    setSaving(false);
  };

  const inputStyle = { width: "100%", padding: "8px 12px", background: C.s2, border: `1px solid ${C.b1}`, borderRadius: 8, color: C.t1, fontSize: 13, fontFamily: mono, outline: "none", boxSizing: "border-box" };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center" }} onClick={onClose}>
      <div style={{ background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 16, padding: 24, width: 420 }} onClick={e => e.stopPropagation()}>
        <div style={{ fontSize: 16, fontWeight: 700, color: C.t1, marginBottom: 16 }}>Adicionar concorrente</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div><div style={{ fontSize: 11, color: C.t3, marginBottom: 4, fontFamily: mono }}>CNPJ</div><input style={inputStyle} value={cnpj} onChange={e => setCnpj(e.target.value)} placeholder="00.000.000/0001-00" /></div>
          <div><div style={{ fontSize: 11, color: C.t3, marginBottom: 4, fontFamily: mono }}>RAZÃO SOCIAL</div><input style={inputStyle} value={nome} onChange={e => setNome(e.target.value)} placeholder="Razão social" /></div>
          <div><div style={{ fontSize: 11, color: C.t3, marginBottom: 4, fontFamily: mono }}>NOME FANTASIA</div><input style={inputStyle} value={fantasia} onChange={e => setFantasia(e.target.value)} placeholder="Nome fantasia" /></div>
          <div><div style={{ fontSize: 11, color: C.t3, marginBottom: 4, fontFamily: mono }}>NOTAS</div><textarea style={{ ...inputStyle, height: 60, resize: "none" }} value={notas} onChange={e => setNotas(e.target.value)} placeholder="Observações sobre o concorrente" /></div>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
          <button onClick={onClose} style={{ padding: "8px 16px", background: C.s3, border: `1px solid ${C.b2}`, borderRadius: 8, color: C.t2, fontSize: 12, cursor: "pointer" }}>Cancelar</button>
          <button onClick={handleSave} disabled={saving} style={{ padding: "8px 16px", background: C.ac, color: "#000", border: "none", borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: "pointer", opacity: saving ? 0.5 : 1 }}>{saving ? "Salvando..." : "Salvar"}</button>
        </div>
      </div>
    </div>
  );
}

export default function ConcorrentePanel() {
  const [concorrentes, setConcorrentes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const [showAdd, setShowAdd] = useState(false);

  const load = async () => {
    setLoading(true); setError("");
    try {
      const resp = await fetch("/api/concorrentes");
      if (!resp.ok) throw new Error(`${resp.status}`);
      setConcorrentes(await resp.json());
    } catch (e) {
      setError("Erro ao carregar concorrentes");
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleImportPncp = async (item) => {
    try {
      await fetch("/api/concorrentes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cnpj: item.cnpj, razao_social: item.razao_social, nome_fantasia: "", segmentos: [], notas: `Importado do PNCP — ${item.participacoes} participações encontradas` }),
      });
      setShowSearch(false);
      load();
    } catch (e) { console.error(e); }
  };

  const handleAddManual = async (data) => {
    try {
      await fetch("/api/concorrentes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      setShowAdd(false);
      load();
    } catch (e) { console.error(e); }
  };

  const handleRemove = async (cnpj) => {
    if (!confirm("Remover este concorrente?")) return;
    try {
      await fetch(`/api/concorrentes/${encodeURIComponent(cnpj)}`, { method: "DELETE" });
      load();
    } catch (e) { console.error(e); }
  };

  if (loading) return <div style={{ fontFamily: mono, fontSize: 12, color: C.t3, padding: 20 }}>Carregando concorrentes...</div>;

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div style={{ fontFamily: mono, fontSize: 9.5, textTransform: "uppercase", letterSpacing: 1.5, color: C.t3 }}>
          Concorrentes ({concorrentes.length})
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button onClick={() => setShowSearch(true)}
            style={{ fontFamily: mono, fontSize: 10, padding: "5px 12px", borderRadius: 6, cursor: "pointer", fontWeight: 600, border: `1px solid ${C.b2}`, background: C.s3, color: C.bl }}>
            🔍 Buscar no PNCP
          </button>
          <button onClick={() => setShowAdd(true)}
            style={{ fontFamily: mono, fontSize: 10, padding: "5px 12px", borderRadius: 6, cursor: "pointer", fontWeight: 600, border: `1px solid ${C.b2}`, background: C.s3, color: C.ac }}>
            + Adicionar
          </button>
        </div>
      </div>

      {error && (
        <div style={{ background: `${C.rd}15`, border: `1px solid ${C.rd}33`, borderRadius: 10, padding: 12, marginBottom: 12 }}>
          <div style={{ fontFamily: mono, fontSize: 12, color: C.rd }}>{error}</div>
        </div>
      )}

      {concorrentes.length === 0 ? (
        <div style={{ background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 14, padding: 32, textAlign: "center" }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🎯</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.t1, marginBottom: 4 }}>Nenhum concorrente cadastrado</div>
          <div style={{ fontSize: 12, color: C.t3, marginBottom: 16 }}>Busque no PNCP ou adicione manualmente para acompanhar seus concorrentes.</div>
          <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
            <button onClick={() => setShowSearch(true)}
              style={{ padding: "8px 20px", background: C.bl, color: "#FFF", border: "none", borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
              Buscar no PNCP
            </button>
            <button onClick={() => setShowAdd(true)}
              style={{ padding: "8px 20px", background: C.s3, color: C.t1, border: `1px solid ${C.b2}`, borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
              Adicionar manual
            </button>
          </div>
        </div>
      ) : (
        <div style={{ background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 14, overflow: "hidden" }}>
          {concorrentes.map((c, i) => {
            const nome = c.nome_fantasia || c.razao_social || c.cnpj;
            const agr = AGR[c.agressividade] || AGR.media;
            const temCnpj = c.cnpj && c.cnpj !== "PREENCHER";
            return (
              <div key={c.cnpj || i} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "12px 16px", borderBottom: i < concorrentes.length - 1 ? `1px solid ${C.b1}` : "none",
                transition: "background 0.15s",
              }}
              onMouseEnter={e => e.currentTarget.style.background = C.s2}
              onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: C.t1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{nome}</div>
                    <Badge text={agr.label} bg={agr.bg} color={agr.color} />
                    {!temCnpj && <Badge text="SEM CNPJ" bg={`${C.am}1a`} color={C.am} />}
                  </div>
                  <div style={{ display: "flex", gap: 12, marginTop: 4, fontFamily: mono, fontSize: 10, color: C.t3 }}>
                    {temCnpj && <span>{c.cnpj}</span>}
                    {c.lances_total > 0 && <span>{c.lances_total} lances · {c.vitorias} vitórias · {c.taxa_vitoria}%</span>}
                    {(c.segmentos || []).length > 0 && <span>{(Array.isArray(c.segmentos) ? c.segmentos : []).slice(0, 3).join(", ")}</span>}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center", flexShrink: 0 }}>
                  {c.desconto_medio > 0 && (
                    <div style={{ fontFamily: mono, fontSize: 11, color: C.am, fontWeight: 600 }}>desc. {c.desconto_medio}%</div>
                  )}
                  <button onClick={() => handleRemove(c.cnpj)}
                    style={{ background: "none", border: "none", color: C.t3, fontSize: 14, cursor: "pointer", padding: "4px 6px", borderRadius: 4 }}
                    onMouseEnter={e => e.currentTarget.style.color = C.rd}
                    onMouseLeave={e => e.currentTarget.style.color = C.t3}
                    title="Remover">
                    ✕
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showSearch && <BuscarPncpModal onClose={() => setShowSearch(false)} onImport={handleImportPncp} />}
      {showAdd && <AddManualModal onClose={() => setShowAdd(false)} onSave={handleAddManual} />}
    </div>
  );
}
