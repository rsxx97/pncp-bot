import { useEffect, useMemo, useState } from "react";

const CRIT_COR = {
  convocacao_documentacao: { cor: "#DC2626", bg: "#FEF2F2", label: "CONVOCAÇÃO DOC", icon: "🚨" },
  pedido_diligencia: { cor: "#DC2626", bg: "#FEF2F2", label: "DILIGÊNCIA", icon: "🔍" },
  mensagem_fornecedor: { cor: "#5A9EF7", bg: "#EFF6FF", label: "FORNECEDOR", icon: "💬" },
};

function corMsg(m) {
  if (m.remetente === "pregoeiro") {
    const cat = m.categoria_label || "";
    if (cat === "convocacao_documentacao" || cat === "pedido_diligencia") {
      return CRIT_COR.convocacao_documentacao;
    }
    return { cor: "#374151", bg: "#F9FAFB", label: "PREGOEIRO", icon: "📢" };
  }
  return CRIT_COR.mensagem_fornecedor;
}

function fmtDataHora(iso) {
  if (!iso) return "";
  try {
    const d = new Date((iso || "").replace(" ", "T"));
    return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
}

export default function ChatModal({ pregao, onClose }) {
  const [filtro, setFiltro] = useState("todas");
  const [historico, setHistorico] = useState([]);
  const s = pregao.snapshot || {};

  // Busca histórico completo do radar_eventos (não perde msgs entre ticks)
  useEffect(() => {
    if (!pregao?.id) return;
    const token = localStorage.getItem("token");
    fetch(`/api/radar/pregoes/${pregao.id}/mensagens`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.ok ? r.json() : { mensagens: [] })
      .then(d => setHistorico(d.mensagens || []))
      .catch(() => setHistorico([]));
  }, [pregao?.id]);

  // Une snapshot atual + histórico, dedup por horário+texto (50 chars)
  const mensagens = useMemo(() => {
    const snap = s.mensagens || [];
    const vistos = new Set();
    const out = [];
    for (const m of [...snap, ...historico]) {
      const k = `${m.horario}|${(m.texto || "").slice(0, 50)}`;
      if (vistos.has(k)) continue;
      vistos.add(k);
      out.push(m);
    }
    return out.sort((a, b) => (b.horario || "").localeCompare(a.horario || ""));
  }, [s.mensagens, historico]);

  const filtradas = useMemo(() => {
    if (filtro === "pregoeiro") return mensagens.filter(m => m.remetente === "pregoeiro");
    if (filtro === "urgentes") return mensagens.filter(m => ["convocacao_documentacao", "pedido_diligencia"].includes(m.categoria_label));
    return mensagens;
  }, [mensagens, filtro]);

  const stats = useMemo(() => ({
    total: mensagens.length,
    pregoeiro: mensagens.filter(m => m.remetente === "pregoeiro").length,
    urgentes: mensagens.filter(m => ["convocacao_documentacao", "pedido_diligencia"].includes(m.categoria_label)).length,
  }), [mensagens]);

  return (
    <>
      <div onClick={onClose} style={{
        position: "fixed", inset: 0, background: "rgba(17,24,39,0.5)", zIndex: 1050,
      }} />
      <div style={{
        position: "fixed", top: "5vh", bottom: "5vh", right: "5vw", left: "5vw",
        maxWidth: 900, margin: "0 auto",
        background: "#FFF", borderRadius: 16, zIndex: 1055,
        display: "flex", flexDirection: "column", overflow: "hidden",
        boxShadow: "0 25px 50px rgba(0,0,0,0.25)",
        fontFamily: "'Ubuntu', system-ui, sans-serif",
      }}>
        {/* Header */}
        <div style={{
          padding: "16px 24px", borderBottom: "1px solid #E5E7EB",
          background: "linear-gradient(180deg,#f9fcff 0%,#f3f7fb 100%)",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 10, padding: "2px 8px", background: "#1A1A18", color: "#FFF", borderRadius: 4, fontWeight: 700, fontFamily: "monospace" }}>
                  {pregao.portal_slug?.toUpperCase()}
                </span>
                <span style={{ fontSize: 13, fontWeight: 700, color: "#1A1A18", fontFamily: "monospace" }}>{pregao.identificador}</span>
              </div>
              <div style={{ fontSize: 13, color: "#1A1A18", fontWeight: 600 }}>{pregao.orgao || s.orgao}</div>
              <div style={{ fontSize: 11, color: "#6B7280", marginTop: 2, display: "-webkit-box", WebkitLineClamp: 1, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                {pregao.objeto || s.objeto}
              </div>
            </div>
            <button onClick={onClose} style={{
              width: 32, height: 32, border: 0, background: "transparent", color: "#6B7280",
              cursor: "pointer", fontSize: 22, lineHeight: 1, padding: 0, borderRadius: 8,
            }}>✕</button>
          </div>
          {/* Stats + Filtros */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 12, flexWrap: "wrap" }}>
            {["todas", "pregoeiro", "urgentes"].map(f => {
              const ativo = filtro === f;
              const count = f === "todas" ? stats.total : f === "pregoeiro" ? stats.pregoeiro : stats.urgentes;
              return (
                <button key={f} onClick={() => setFiltro(f)}
                  style={{
                    padding: "4px 12px", fontSize: 11, fontWeight: 600,
                    background: ativo ? "#1A1A18" : "#fff",
                    color: ativo ? "#fff" : "#374151",
                    border: `1px solid ${ativo ? "#1A1A18" : "#D1D5DB"}`,
                    borderRadius: 999, cursor: "pointer", textTransform: "capitalize",
                  }}>
                  {f === "urgentes" ? "🚨 urgentes" : f} ({count})
                </button>
              );
            })}
          </div>
        </div>

        {/* Lista de mensagens */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 24px", background: "#FAFBFC" }}>
          {filtradas.length === 0 ? (
            <FallbackEventos pregao={pregao} />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {filtradas.map((m, i) => {
                const c = corMsg(m);
                return (
                  <div key={m.id || i} style={{
                    background: c.bg, borderLeft: `3px solid ${c.cor}`,
                    borderRadius: 8, padding: "10px 14px",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                      <span style={{ fontSize: 14 }}>{c.icon}</span>
                      <span style={{ fontSize: 9, fontWeight: 700, color: c.cor, textTransform: "uppercase", letterSpacing: 0.5 }}>
                        {c.label}
                      </span>
                      {m.destinatario_cnpj && (
                        <span style={{ fontSize: 9, color: "#6B7280", fontFamily: "monospace" }}>
                          → {m.destinatario_cnpj}
                        </span>
                      )}
                      <span style={{ fontSize: 10, color: "#9CA3AF", marginLeft: "auto", fontFamily: "monospace" }}>
                        {fmtDataHora(m.horario)}
                      </span>
                    </div>
                    <div style={{ fontSize: 13, color: "#1A1A18", lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
                      {m.texto}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: "12px 24px", borderTop: "1px solid #E5E7EB",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          background: "#fff", fontSize: 11, color: "#6B7280",
        }}>
          <span>{filtradas.length} de {mensagens.length} mensagens</span>
          <button onClick={onClose}
            style={{ padding: "6px 14px", background: "#1A1A18", color: "#fff", border: 0, borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
            Fechar
          </button>
        </div>
      </div>
    </>
  );
}

// Quando não tem mensagens de chat, mostra os eventos detectados pelo radar
function FallbackEventos({ pregao }) {
  const eventos = pregao.ultimos_eventos || [];
  if (eventos.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: 40, color: "#9CA3AF", fontSize: 13 }}>
        <div style={{ fontSize: 32, marginBottom: 8 }}>📭</div>
        Nenhuma mensagem nem evento ainda<br/>
        <span style={{ fontSize: 11, color: "#D1D5DB" }}>O radar avisa quando o pregoeiro publicar alguma coisa</span>
      </div>
    );
  }
  return (
    <div>
      <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 10, fontFamily: "monospace", textTransform: "uppercase", letterSpacing: 0.5 }}>
        Últimos eventos detectados ({eventos.length})
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {eventos.map(e => {
          const urg = e.criticidade === "urgente";
          const cor = urg ? "#DC2626" : "#5A9EF7";
          return (
            <div key={e.id} style={{
              background: urg ? "#FEF2F2" : "#EFF6FF", borderLeft: `3px solid ${cor}`,
              borderRadius: 8, padding: "10px 14px",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                <span style={{ fontSize: 9, fontWeight: 700, color: cor, textTransform: "uppercase", letterSpacing: 0.5, fontFamily: "monospace" }}>
                  {e.tipo}
                </span>
                <span style={{ fontSize: 10, color: "#9CA3AF", marginLeft: "auto", fontFamily: "monospace" }}>
                  {fmtDataHora(e.criado_em)}
                </span>
              </div>
              {e.titulo && <div style={{ fontSize: 12, color: "#1A1A18", fontWeight: 600 }}>{e.titulo}</div>}
              {e.descricao && <div style={{ fontSize: 12, color: "#374151", marginTop: 2 }}>{e.descricao}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
