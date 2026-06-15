import { useMemo, useState, useEffect } from "react";

const CRIT_STYLE = {
  urgente: { label: "URGENTE", color: "#DC2626", bg: "linear-gradient(180deg, #fff5f5 0%, #fffafa 100%)", border: "#DC2626" },
  alta:    { label: "ALTA",    color: "#F7931E", bg: "linear-gradient(180deg, #fff8ef 0%, #fffaf3 100%)", border: "#F7931E" },
  normal:  { label: "NORMAL",  color: "#2684FF", bg: "linear-gradient(180deg, #eef7ff 0%, #f8fbff 100%)", border: "#2684FF" },
};

const ICONE_TIPO = {
  SESSAO_ABERTA: "🟢",
  SESSAO_SUSPENSA: "⏸️",
  SESSAO_RETOMADA: "▶️",
  SESSAO_ENCERRADA: "🏁",
  NOVO_LANCE: "💰",
  USUARIO_SUPERADO: "📉",
  USUARIO_NA_FRENTE: "📈",
  MENSAGEM_PREGOEIRO: "💬",
  MUDANCA_FASE: "🔄",
  CONVOCACAO_PROPOSTA: "📋",
  CONVOCACAO_DOCUMENTACAO: "📑",
  PEDIDO_DILIGENCIA: "🔍",
  CONTRAPROPOSTA: "🤝",
  HABILITADO: "✅",
  INABILITADO: "❌",
  RECURSO_ABERTO: "⚖️",
  RECURSO_JULGADO: "🧑‍⚖️",
  ADJUDICADO: "🥇",
  HOMOLOGADO: "🏆",
  FRACASSADO: "💥",
  DESERTO: "🌵",
  REPUBLICACAO: "🔁",
  ADIAMENTO: "⏰",
  CANCELAMENTO: "🚫",
};

function tempoRelativo(iso) {
  const t = new Date(iso).getTime();
  const diff = Date.now() - t;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `há ${h}h`;
  const d = Math.floor(h / 24);
  if (d < 7) return `há ${d}d`;
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

export default function EventFeed({ eventos, onMarcarLido, onMarcarTodosLidos, onFechar }) {
  const [selecionados, setSelecionados] = useState(new Set());
  const [filtro, setFiltro] = useState("nao_lidas"); // "todas" | "nao_lidas" | "urgentes"

  const naoLidos = useMemo(() => eventos.filter(e => !e.lido_em).length, [eventos]);
  const urgentes = useMemo(() => eventos.filter(e => e.criticidade === "urgente").length, [eventos]);
  const todosLidos = naoLidos === 0;

  const eventosVisiveis = useMemo(() => {
    if (filtro === "nao_lidas") return eventos.filter(e => !e.lido_em);
    if (filtro === "urgentes") return eventos.filter(e => e.criticidade === "urgente");
    return eventos;
  }, [eventos, filtro]);

  useEffect(() => {
    setSelecionados(prev => {
      const next = new Set();
      eventos.forEach(e => { if (prev.has(e.id)) next.add(e.id); });
      return next;
    });
  }, [eventos]);

  const toggle = (id) => {
    setSelecionados(prev => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  };

  const toggleTodos = () => {
    if (selecionados.size === eventosVisiveis.length) {
      setSelecionados(new Set());
    } else {
      setSelecionados(new Set(eventosVisiveis.map(e => e.id)));
    }
  };

  const marcarSelecionadosLidos = async () => {
    const ids = [...selecionados];
    await Promise.all(ids.map(id => {
      const e = eventos.find(x => x.id === id);
      return e && !e.lido_em ? onMarcarLido(id) : Promise.resolve();
    }));
    setSelecionados(new Set());
  };

  const todosMarcados = selecionados.size > 0 && selecionados.size === eventos.length;

  return (
    <>
      <div onClick={onFechar} style={{
        position: "fixed", inset: 0, background: "rgba(17,24,39,0.38)", zIndex: 1040,
      }} />

      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0, zIndex: 1045,
        display: "flex", flexDirection: "column",
        width: "min(420px, calc(100vw - 18px))",
        margin: "0.75rem",
        borderRadius: 24,
        background: "linear-gradient(180deg, #f9fcff 0%, #f3f7fb 100%)",
        border: "1px solid rgba(31,55,74,0.08)",
        boxShadow: "0 18px 45px rgba(18,45,68,0.18)",
        overflow: "hidden",
        fontFamily: "'Ubuntu', system-ui, sans-serif",
        color: "#1f374a",
      }}>
        {/* Header */}
        <div style={{
          padding: "1rem 1.15rem 0.9rem",
          borderBottom: "1px solid rgba(31,55,74,0.08)",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem",
        }}>
          <div>
            <h5 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#1f374a", whiteSpace: "nowrap" }}>
              <span style={{ marginRight: 8 }}>🔔</span>
              Notificações:
              <span style={{
                display: "inline-block", padding: 4, borderRadius: 5, background: "#eef1f4",
                color: "#1f374a", fontSize: 16, fontWeight: 700, lineHeight: 1, marginLeft: 8,
              }}>
                {eventos.length}
              </span>
            </h5>
            <div style={{ marginTop: 4, color: "#607385", fontSize: 12 }}>
              {naoLidos > 0 ? `${naoLidos} não lida${naoLidos > 1 ? "s" : ""}` : "Tudo em dia"}
            </div>
          </div>
          <button onClick={onFechar} style={{
            width: 28, height: 28, border: 0, background: "transparent", color: "#b8b8b8",
            cursor: "pointer", fontSize: 20, lineHeight: 1, padding: 0,
          }}>✕</button>
        </div>

        {/* Filtro */}
        {eventos.length > 0 && (
          <div style={{ padding: "0.5rem 1.15rem 0.75rem", display: "flex", gap: 6, flexWrap: "wrap" }}>
            {[
              { k: "nao_lidas", label: "Não lidas", count: naoLidos },
              { k: "urgentes", label: "🚨 Urgentes", count: urgentes },
              { k: "todas", label: "Todas", count: eventos.length },
            ].map(f => {
              const ativo = filtro === f.k;
              return (
                <button key={f.k} onClick={() => setFiltro(f.k)}
                  style={{
                    padding: "4px 12px", fontSize: 11, fontWeight: 600,
                    background: ativo ? "#2684FF" : "#fff",
                    color: ativo ? "#fff" : "#1f374a",
                    border: `1px solid ${ativo ? "#2684FF" : "rgba(31,55,74,0.15)"}`,
                    borderRadius: 999, cursor: "pointer",
                  }}>
                  {f.label} ({f.count})
                </button>
              );
            })}
          </div>
        )}

        {/* Marcar todos */}
        {eventosVisiveis.length > 0 && (
          <div style={{ padding: "0 1.15rem 0.5rem" }}>
            <label style={{
              display: "flex", alignItems: "center", gap: "0.9rem", width: "100%",
              padding: 10, borderRadius: 8, background: "rgba(31,55,74,0.05)",
              color: "#1f374a", fontSize: 12, fontWeight: 600, cursor: "pointer",
            }}>
              <input type="checkbox" checked={todosMarcados}
                onChange={toggleTodos}
                style={{
                  width: 16, height: 16, accentColor: "#2684FF", cursor: "pointer", margin: 0,
                }} />
              <span>Selecionar visíveis ({eventosVisiveis.length})</span>
            </label>
          </div>
        )}

        {/* Lista */}
        <div style={{ flex: 1, minHeight: 0, padding: 16, overflowY: "auto" }}>
          {eventosVisiveis.length === 0 ? (
            <div style={{
              padding: "2.5rem 1rem", color: "#607385", fontSize: 13, textAlign: "center",
              background: "rgba(255,255,255,0.7)",
              border: "1px dashed rgba(31,55,74,0.14)", borderRadius: 20,
            }}>
              {filtro === "nao_lidas" ? "✓ Tudo lido" : filtro === "urgentes" ? "Nenhum urgente" : "Nenhuma notificação"}
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.8rem" }}>
              {eventosVisiveis.map(e => {
                const crit = CRIT_STYLE[e.criticidade] || CRIT_STYLE.normal;
                const unread = !e.lido_em;
                const checked = selecionados.has(e.id);
                return (
                  <div key={e.id} style={{
                    position: "relative",
                    display: "grid", gridTemplateColumns: "28px minmax(0, 1fr)", gap: "0.9rem",
                    padding: "0.95rem", borderRadius: 20,
                    border: `2px solid ${unread ? crit.border : "rgba(31,55,74,0.08)"}`,
                    background: unread ? crit.bg : "rgba(255,255,255,0.92)",
                    boxShadow: "0 10px 22px rgba(18,45,68,0.08)",
                    transition: "transform .15s ease, box-shadow .15s ease",
                  }}>
                    {/* Checkbox */}
                    <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "center", paddingTop: 4 }}>
                      <input type="checkbox" checked={checked}
                        onChange={() => toggle(e.id)}
                        style={{
                          width: 16, height: 16, accentColor: "#2684FF", cursor: "pointer", margin: 0,
                        }} />
                    </div>

                    {/* Conteúdo */}
                    <div
                      onClick={() => unread && onMarcarLido(e.id)}
                      style={{ cursor: unread ? "pointer" : "default", minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                        <span style={{ fontSize: 18 }}>{ICONE_TIPO[e.tipo] || "🔔"}</span>
                        <span style={{
                          fontSize: 10, fontFamily: "monospace", fontWeight: 700, color: crit.color,
                          padding: "2px 6px", borderRadius: 4, background: "rgba(255,255,255,0.6)",
                        }}>
                          {crit.label}
                        </span>
                        <span style={{
                          fontSize: 11, color: unread ? crit.color : "#B3B3B2",
                          marginLeft: "auto", whiteSpace: "nowrap",
                        }}>
                          {tempoRelativo(e.criado_em)}
                        </span>
                      </div>

                      <div style={{
                        color: "#1f374a", fontSize: 13, lineHeight: 1.45, wordBreak: "break-word",
                        fontWeight: unread ? 600 : 500,
                      }}>
                        {e.titulo}
                      </div>

                      {e.descricao && (
                        <div style={{
                          color: "#607385", fontSize: 12, lineHeight: 1.45, marginTop: 4,
                          wordBreak: "break-word",
                        }}>
                          {e.descricao}
                        </div>
                      )}

                      <div style={{
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                        gap: 12, marginTop: 8,
                      }}>
                        <span style={{
                          display: "inline-flex", alignItems: "center", gap: 6,
                          color: unread ? crit.color : "#B3B3B2", fontSize: 11, fontWeight: 700,
                        }}>
                          <span style={{
                            width: 8, height: 8, borderRadius: 999,
                            background: unread ? crit.color : "#c4ced8",
                          }} />
                          {unread ? "NÃO LIDA" : "LIDA"}
                        </span>
                        {e.portal_slug && (
                          <span style={{
                            fontSize: 10, fontFamily: "monospace", color: "#607385",
                            padding: "2px 6px", borderRadius: 4, background: "rgba(31,55,74,0.06)",
                          }}>
                            {e.portal_slug.toUpperCase()}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Bulk actions / Marcar todos */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16,
          padding: "0.95rem 1.15rem 1.15rem",
          borderTop: "1px solid rgba(31,55,74,0.08)",
          background: "rgba(255,255,255,0.86)",
        }}>
          {selecionados.size > 0 ? (
            <button onClick={marcarSelecionadosLidos}
              style={{
                width: "100%", padding: "0.95rem 1.35rem", borderRadius: 10,
                background: "#2684FF", color: "#fff",
                fontSize: 14, fontWeight: 600, border: 0, cursor: "pointer",
                display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6,
              }}>
              ✓ Marcar (<b>{selecionados.size}</b>) como Lida{selecionados.size > 1 ? "s" : ""}
            </button>
          ) : (
            <button onClick={onMarcarTodosLidos} disabled={todosLidos}
              style={{
                width: "100%", padding: "0.95rem 1.35rem", borderRadius: 10,
                background: todosLidos ? "#cbd5e0" : "#2684FF",
                color: "#fff", fontSize: 14, fontWeight: 600, border: 0,
                cursor: todosLidos ? "not-allowed" : "pointer",
                display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6,
              }}>
              ✓ Marcar todas como lidas
            </button>
          )}
        </div>
      </div>
    </>
  );
}
