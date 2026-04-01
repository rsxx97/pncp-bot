import { useState } from "react";
import { api } from "../api";

function formatBRL(v) {
  if (v == null || v === 0) return "N/I";
  if (v >= 1e6) return `R$ ${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `R$ ${(v / 1e3).toFixed(0)}K`;
  return `R$ ${v.toFixed(0)}`;
}

const UFS = [
  "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
  "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"
];

export default function PncpSearch({ onImported }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [addingId, setAddingId] = useState(null);

  // Filtros
  const [uf, setUf] = useState("RJ");
  const [municipio, setMunicipio] = useState("");
  const [modalidade, setModalidade] = useState("");
  const [valorMin, setValorMin] = useState("");
  const [valorMax, setValorMax] = useState("");
  const [statusFiltro, setStatusFiltro] = useState("");

  const buscar = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setResults(null);
    try {
      const filtros = {};
      if (uf) filtros.uf = uf;
      if (municipio) filtros.municipio = municipio;
      if (modalidade) filtros.modalidade = modalidade;
      if (valorMin) filtros.valor_min = valorMin;
      if (valorMax) filtros.valor_max = valorMax;
      if (statusFiltro) filtros.status_pncp = statusFiltro;
      const data = await api.buscarPncp(query.trim(), filtros);
      setResults(data.items || []);
    } catch (e) {
      console.error(e);
      setResults([]);
    }
    setLoading(false);
  };

  const adicionarPipeline = async (pncpId) => {
    setAddingId(pncpId);
    try {
      await api.importarPncp([pncpId]);
      setResults(prev => prev.map(r => r.pncp_id === pncpId ? { ...r, ja_importado: true } : r));
      onImported?.();
    } catch (e) {
      console.error(e);
    }
    setAddingId(null);
  };

  const inputStyle = { padding: "8px 12px", border: "1px solid #DDD", borderRadius: 8, fontSize: 14 };
  const selectStyle = { ...inputStyle, background: "#FFF", minWidth: 100 };

  return (
    <div>
      <div style={{ fontSize: 18, fontWeight: 700, color: "#1A1A18", marginBottom: 4 }}>
        Oportunidades PNCP
      </div>
      <div style={{ fontSize: 13, color: "#8A8A85", marginBottom: 16 }}>
        Busque editais no portal e adicione ao pipeline os que interessam
      </div>

      {/* Search bar */}
      <div style={{ display: "flex", gap: 10, marginBottom: 12, alignItems: "center", flexWrap: "wrap" }}>
        <input
          placeholder="Ex: limpeza conservacao predial"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === "Enter" && buscar()}
          style={{ ...inputStyle, flex: 1, minWidth: 250 }}
        />
        <button onClick={buscar} disabled={loading}
          style={{ padding: "8px 20px", borderRadius: 8, border: "none", fontSize: 14, fontWeight: 600, cursor: "pointer", background: "#1A1A18", color: "#FFF" }}>
          {loading ? "Buscando..." : "Buscar"}
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, marginBottom: 20, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <label style={{ fontSize: 12, color: "#8A8A85", fontWeight: 500 }}>UF</label>
          <select value={uf} onChange={e => setUf(e.target.value)} style={selectStyle}>
            <option value="">Todas</option>
            {UFS.map(u => <option key={u} value={u}>{u}</option>)}
          </select>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <label style={{ fontSize: 12, color: "#8A8A85", fontWeight: 500 }}>Municipio</label>
          <input placeholder="Filtrar..." value={municipio} onChange={e => setMunicipio(e.target.value)}
            style={{ ...inputStyle, width: 140, fontSize: 13 }} />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <label style={{ fontSize: 12, color: "#8A8A85", fontWeight: 500 }}>Modalidade</label>
          <select value={modalidade} onChange={e => setModalidade(e.target.value)} style={selectStyle}>
            <option value="">Todas</option>
            <option value="Pregão Eletrônico">Pregão Eletrônico</option>
            <option value="Pregão Presencial">Pregão Presencial</option>
            <option value="Concorrência">Concorrência</option>
            <option value="Concorrência - Loss">Concorrência (Loss)</option>
            <option value="Dispensa">Dispensa de Licitação</option>
            <option value="Inexigibilidade">Inexigibilidade</option>
            <option value="Manifestação de Interesse">Manifestação de Interesse</option>
            <option value="Credenciamento">Credenciamento</option>
            <option value="Leilão">Leilão</option>
            <option value="Diálogo Competitivo">Diálogo Competitivo</option>
          </select>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <label style={{ fontSize: 12, color: "#8A8A85", fontWeight: 500 }}>Status</label>
          <select value={statusFiltro} onChange={e => setStatusFiltro(e.target.value)} style={selectStyle}>
            <option value="">Todos</option>
            <option value="recebendo">A Receber/Recebendo Proposta</option>
            <option value="julgamento">Em Julgamento/Propostas Encerradas</option>
            <option value="encerradas">Encerradas</option>
          </select>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <label style={{ fontSize: 12, color: "#8A8A85", fontWeight: 500 }}>Valor</label>
          <input placeholder="Min" value={valorMin} onChange={e => setValorMin(e.target.value.replace(/[^0-9]/g, ""))}
            style={{ ...inputStyle, width: 80, fontSize: 13, textAlign: "right" }} />
          <span style={{ fontSize: 12, color: "#AEAEA8" }}>a</span>
          <input placeholder="Max" value={valorMax} onChange={e => setValorMax(e.target.value.replace(/[^0-9]/g, ""))}
            style={{ ...inputStyle, width: 80, fontSize: 13, textAlign: "right" }} />
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ textAlign: "center", padding: 40, color: "#8A8A85" }}>
          <svg width="28" height="28" viewBox="0 0 24 24" style={{ animation: "spin 1s linear infinite", marginBottom: 8 }}>
            <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
            <circle cx="12" cy="12" r="10" stroke="#8A8A85" strokeWidth="2.5" fill="none" strokeDasharray="31 31" strokeLinecap="round" />
          </svg>
          <div>Consultando PNCP...</div>
        </div>
      )}

      {/* Results */}
      {results && !loading && (() => {
        return (
        <>
          <div style={{ fontSize: 14, color: "#8A8A85", marginBottom: 12 }}>
            {results.length} oportunidades encontradas {statusFiltro && `(${statusFiltro})`}
          </div>

          {results.length === 0 && (
            <div style={{ textAlign: "center", padding: 40, color: "#AEAEA8" }}>
              Nenhuma oportunidade encontrada. Tente outros termos ou remova filtros.
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {results.map(r => (
              <div key={r.pncp_id}
                style={{
                  background: r.ja_importado ? "#F0FDF4" : "#FFF",
                  border: `1px solid ${r.ja_importado ? "#BBF7D0" : "#E8E8E4"}`,
                  borderRadius: 10, padding: 14,
                }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                  <div style={{ flex: 1 }}>
                    <span style={{ fontSize: 14, fontWeight: 600, color: "#1A1A18" }}>{r.orgao}</span>
                    <span style={{ fontSize: 14, fontWeight: 700, color: "#065F46", marginLeft: 12 }}>{formatBRL(r.valor_estimado)}</span>
                  </div>
                  <div>
                    {r.ja_importado ? (
                      <span style={{ background: "#D1FAE5", color: "#065F46", padding: "4px 12px", borderRadius: 8, fontSize: 12, fontWeight: 600 }}>
                        No pipeline
                      </span>
                    ) : (
                      <button
                        onClick={() => adicionarPipeline(r.pncp_id)}
                        disabled={addingId === r.pncp_id}
                        style={{
                          padding: "6px 14px", borderRadius: 8, border: "none", fontSize: 12, fontWeight: 600,
                          cursor: "pointer", background: "#1A1A18", color: "#FFF",
                        }}>
                        {addingId === r.pncp_id ? "Adicionando..." : "+ Pipeline"}
                      </button>
                    )}
                  </div>
                </div>
                <div style={{ fontSize: 13, color: "#4A4A48", lineHeight: 1.4, marginBottom: 6 }}>
                  {r.objeto?.length > 180 ? r.objeto.substring(0, 180) + "..." : r.objeto}
                </div>
                <div style={{ fontSize: 11, color: "#AEAEA8", display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                  <span>{r.modalidade}</span>
                  <span>{r.uf}{r.municipio ? ` - ${r.municipio}` : ""}</span>
                  {r.data_encerramento && <span>Encerra: {r.data_encerramento.split("T")[0]}</span>}
                  {r.link_edital && (
                    <a href={r.link_edital} target="_blank" rel="noreferrer"
                      onClick={e => e.stopPropagation()}
                      style={{ color: "#3B82F6", textDecoration: "none", fontWeight: 500 }}>
                      Ver no PNCP
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
        );
      })()}

      {/* Empty state */}
      {!results && !loading && (
        <div style={{ textAlign: "center", padding: 60, color: "#AEAEA8" }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>🔍</div>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>Busque oportunidades no PNCP</div>
          <div style={{ fontSize: 13 }}>Digite palavras-chave do objeto e clique em Buscar</div>
        </div>
      )}
    </div>
  );
}
