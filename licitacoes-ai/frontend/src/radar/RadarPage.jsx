import { useCallback, useEffect, useMemo, useState } from "react";
import { radarApi } from "./api";
import useRadarSSE from "./useRadarSSE";
import useNotificationSound from "./useNotificationSound";
import ConnectionIndicator from "./ConnectionIndicator";
import EventFeed from "./EventFeed";
import ChatModal from "./ChatModal";

// ── Criticidade 4 níveis (inspirado eLicitaRadar) ─────────────────────
const NIVEIS = {
  leve:     { label: "Leve",     cor: "#06B6D4", bg: "#0E2A33" },
  moderado: { label: "Moderado", cor: "#22C55E", bg: "#0E2A1A" },
  grave:    { label: "Grave",    cor: "#F59E0B", bg: "#2A1E0E" },
  urgente:  { label: "Urgente",  cor: "#DC2626", bg: "#2A0E0E" },
};
const NIVEL_ORDEM = ["urgente", "grave", "moderado", "leve"];

function derivarNivel(pregao) {
  const evs = pregao.ultimos_eventos || [];
  // Se algum evento é urgente, e ainda não foi lido (não sabemos lido_em aqui — usar últimos eventos como aproximação)
  const temUrgente = evs.some(e => (e.criticidade || "").toLowerCase() === "urgente");
  if (temUrgente) return "urgente";
  // grave: 1+ eventos recentes (últimas 24h)
  const agora = Date.now();
  const recentes = evs.filter(e => {
    if (!e.criado_em) return false;
    const t = new Date(e.criado_em).getTime();
    return !isNaN(t) && agora - t < 24 * 3600 * 1000;
  });
  if (recentes.length >= 3) return "grave";
  if (recentes.length >= 1) return "moderado";
  return "leve";
}

function extrairUF(pregao) {
  const orgao = pregao.orgao || pregao.snapshot?.orgao || "";
  // Pegar UF do final do nome do órgão (ex: "PREF.MUN.DE JAPERI/RJ")
  const m = orgao.match(/[\/\s-]([A-Z]{2})\b/);
  if (m) return m[1];
  // Tentar do snapshot
  if (pregao.snapshot?.uf) return pregao.snapshot.uf;
  return "—";
}

const PAGE_SIZES = [10, 25, 50, 100];

const fmtDataHora = (iso) => {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch { return "—"; }
};

function NotificationBell({ naoLidas, urgentes, onClick }) {
  const tem = naoLidas > 0;
  const temUrgente = urgentes > 0;
  return (
    <button onClick={onClick} title={tem ? `${naoLidas} não lidas` : "Notificações"}
      style={{
        position: "relative", width: 36, height: 36, border: 0, background: "transparent",
        color: "#EEEEE8", cursor: "pointer", borderRadius: 8,
        display: "inline-flex", alignItems: "center", justifyContent: "center",
      }}>
      <span style={{ fontSize: 18, lineHeight: 1, animation: temUrgente ? "bell-shake 1.2s ease-in-out infinite" : "none", display: "inline-block" }}>🔔</span>
      {tem && (
        <span style={{
          position: "absolute", top: -2, right: -2, minWidth: 18, height: 18, padding: "0 5px",
          borderRadius: 999, border: "2px solid #0F0F12",
          background: temUrgente ? "#DC2626" : "#F7931E",
          color: "#fff", fontSize: 10, fontWeight: 700, lineHeight: "14px",
          display: "inline-flex", alignItems: "center", justifyContent: "center",
          animation: temUrgente ? "bell-pulse 1.6s ease-in-out infinite" : "none",
        }}>
          {naoLidas > 99 ? "99+" : naoLidas}
        </span>
      )}
    </button>
  );
}

export default function RadarPage() {
  const [pregoes, setPregoes] = useState([]);
  const [portais, setPortais] = useState([]);
  const [tab, setTab] = useState("monitorando");

  const [filtroPortal, setFiltroPortal] = useState("");
  const [filtroUF, setFiltroUF] = useState("");
  const [filtroNivel, setFiltroNivel] = useState("");
  const [filtroStatus, setFiltroStatus] = useState("todos");
  const [busca, setBusca] = useState("");

  // Paginação
  const [pagina, setPagina] = useState(1);
  const [pageSize, setPageSize] = useState(() => {
    try { return Number(localStorage.getItem("radar_page_size")) || 10; } catch { return 10; }
  });

  const [feedAberto, setFeedAberto] = useState(false);
  const [eventos, setEventos] = useState([]);
  const [flashIds, setFlashIds] = useState(new Set());
  const [showModal, setShowModal] = useState(false);
  const [pregaoChat, setPregaoChat] = useState(null);

  const [audioLiberado, setAudioLiberado] = useState(() => {
    try { return localStorage.getItem("radar_audio_liberado") === "1"; } catch { return false; }
  });
  const { tocar } = useNotificationSound();

  const carregar = useCallback(async () => {
    const params = {};
    if (filtroStatus !== "todos") params.status = filtroStatus;
    if (filtroPortal) params.portal = filtroPortal;
    if (busca) params.busca = busca;
    setPregoes(await radarApi.listarPregoes(params));
  }, [filtroStatus, filtroPortal, busca]);

  useEffect(() => { carregar(); }, [carregar]);
  useEffect(() => { radarApi.listarPortais().then(setPortais); }, []);
  useEffect(() => { radarApi.historico({ dias: 7, limite: 50 }).then(setEventos); }, []);

  // Reset página quando filtros/tab mudam
  useEffect(() => { setPagina(1); }, [tab, filtroPortal, filtroUF, filtroNivel, filtroStatus, busca]);
  useEffect(() => { try { localStorage.setItem("radar_page_size", String(pageSize)); } catch {} }, [pageSize]);

  const handleEvent = useCallback((data) => {
    if (data.evento) {
      const e = data.evento;
      setEventos(prev => {
        const semDup = prev.filter(x => x.id !== e.id);
        return [{ ...e, criado_em: e.criado_em || new Date().toISOString() }, ...semDup].slice(0, 200);
      });
      if (audioLiberado) tocar(e.criticidade === "urgente");
      setFlashIds(prev => new Set(prev).add(e.pregao_monitorado_id));
      setTimeout(() => {
        setFlashIds(prev => { const n = new Set(prev); n.delete(e.pregao_monitorado_id); return n; });
      }, 2500);
      carregar();
    }
  }, [carregar, audioLiberado, tocar]);

  const { status } = useRadarSSE(handleEvent);

  const liberarAudio = () => {
    setAudioLiberado(true);
    try { localStorage.setItem("radar_audio_liberado", "1"); } catch {}
    tocar(false);
  };

  const toggleFavorito = async (p) => {
    const novo = !p.favorito;
    // Update otimista
    setPregoes(prev => prev.map(x => x.id === p.id ? { ...x, favorito: novo ? 1 : 0 } : x));
    try { await radarApi.favoritar(p.id, novo); }
    catch (e) {
      setPregoes(prev => prev.map(x => x.id === p.id ? { ...x, favorito: p.favorito } : x));
    }
  };

  // Enriquecer pregões com nível e UF
  const pregoesEnriquecidos = useMemo(() => pregoes.map(p => ({
    ...p, _nivel: derivarNivel(p), _uf: extrairUF(p), _favorito: !!p.favorito,
  })), [pregoes]);

  const ufsDisponiveis = useMemo(() => [...new Set(pregoesEnriquecidos.map(p => p._uf).filter(u => u && u !== "—"))].sort(), [pregoesEnriquecidos]);

  const filtrados = useMemo(() => {
    let r = pregoesEnriquecidos;
    if (tab === "favoritas") r = r.filter(p => p._favorito);
    if (filtroUF) r = r.filter(p => p._uf === filtroUF);
    if (filtroNivel) r = r.filter(p => p._nivel === filtroNivel);
    return r;
  }, [pregoesEnriquecidos, tab, filtroUF, filtroNivel]);

  // Paginação
  const totalPaginas = Math.max(1, Math.ceil(filtrados.length / pageSize));
  const paginaAtual = Math.min(pagina, totalPaginas);
  const inicioPag = (paginaAtual - 1) * pageSize;
  const paginados = filtrados.slice(inicioPag, inicioPag + pageSize);

  const ativos = pregoes.filter(p => p.status === "em_sessao").length;
  const naoLidas = eventos.filter(e => !e.lido_em).length;
  const urgentes = eventos.filter(e => !e.lido_em && e.criticidade === "urgente").length;

  // Estatísticas 30d por criticidade — paridade eLicita
  const stats30d = useMemo(() => {
    const agora = Date.now();
    const limite30d = agora - 30 * 24 * 3600 * 1000;
    const recentes = eventos.filter(e => {
      const t = e.criado_em ? new Date(e.criado_em).getTime() : 0;
      return t >= limite30d;
    });
    const naoLidasRecentes = recentes.filter(e => !e.lido_em);
    const por = (crit) => naoLidasRecentes.filter(e => (e.criticidade || "leve").toLowerCase() === crit).length;
    return {
      urgente: por("urgente"),
      grave: por("grave") + naoLidasRecentes.filter(e => e.tipo === "convocacao" || e.tipo === "diligencia").length,
      moderado: por("moderado") + naoLidasRecentes.filter(e => e.tipo === "aviso").length,
      leve: por("leve"),
    };
  }, [eventos]);

  return (
    <div style={{ position: "relative" }}>
      <style>{`
        @keyframes bell-shake {
          0%, 100% { transform: rotate(0deg); }
          10%, 30% { transform: rotate(-12deg); }
          20%, 40% { transform: rotate(12deg); }
        }
        @keyframes bell-pulse {
          0% { box-shadow: 0 0 0 0 rgba(220,38,38,0.7); }
          70% { box-shadow: 0 0 0 8px rgba(220,38,38,0); }
        }
        @keyframes rowFlash {
          0% { background: rgba(190,255,58,0.18); }
          100% { background: transparent; }
        }
      `}</style>

      {/* Header com ações */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <ConnectionIndicator status={status} />
          <span style={{ fontSize: 12, color: "#98968E", fontFamily: "monospace" }}>
            {ativos} em sessão · {pregoes.length} monitorados
          </span>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {!audioLiberado && (
            <button onClick={liberarAudio}
              style={{ padding: "6px 12px", fontSize: 11, background: "#FFB038", color: "#1A1A18", border: "none", borderRadius: 6, cursor: "pointer", fontWeight: 700 }}>
              🔔 Ativar som
            </button>
          )}
          <NotificationBell naoLidas={naoLidas} urgentes={urgentes} onClick={() => setFeedAberto(!feedAberto)} />
          <button onClick={() => setShowModal(true)}
            style={{ padding: "7px 14px", fontSize: 11, background: "#BEFF3A", color: "#1A1A18", border: "none", borderRadius: 6, cursor: "pointer", fontWeight: 700, letterSpacing: 0.3 }}>
            + MONITORAR
          </button>
        </div>
      </div>

      {/* Painel de estatísticas 30 dias por criticidade — paridade eLicita */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 18 }}>
        {NIVEL_ORDEM.map(k => {
          const n = NIVEIS[k];
          const v = stats30d[k] || 0;
          return (
            <div key={k} onClick={() => setFiltroNivel(filtroNivel === k ? "" : k)}
              style={{
                background: "#111114", border: `1px solid ${filtroNivel === k ? n.cor : "#2A2A32"}`,
                borderLeft: `4px solid ${n.cor}`, borderRadius: 8, padding: "12px 14px",
                cursor: "pointer", transition: "border-color 0.15s",
                display: "flex", flexDirection: "column", gap: 4,
              }}>
              <span style={{ fontSize: 10, fontFamily: "monospace", color: n.cor, fontWeight: 700, letterSpacing: 0.8, textTransform: "uppercase" }}>
                {n.label}
              </span>
              <span style={{ fontSize: 22, fontWeight: 700, color: "#EEEEE8" }}>{v}</span>
              <span style={{ fontSize: 10, color: "#5A5854", fontFamily: "monospace" }}>30 dias · não lidas</span>
            </div>
          );
        })}
      </div>

      {/* Tabs Monitorando / Favoritas */}
      <div style={{ display: "flex", gap: 0, borderBottom: "1px solid #2A2A32", marginBottom: 10 }}>
        {[{ k: "monitorando", l: `Monitorando (${pregoesEnriquecidos.filter(p => tab !== "favoritas" || p._favorito).length})` },
          { k: "favoritas", l: `Favoritas (${pregoesEnriquecidos.filter(p => p._favorito).length})` }].map(t => (
          <button key={t.k} onClick={() => setTab(t.k)}
            style={{
              padding: "10px 18px", fontSize: 11, background: "transparent", border: 0,
              borderBottom: tab === t.k ? "2px solid #BEFF3A" : "2px solid transparent",
              color: tab === t.k ? "#EEEEE8" : "#5A5854",
              cursor: "pointer", fontWeight: 600, fontFamily: "monospace",
              textTransform: "uppercase", letterSpacing: 0.8, marginBottom: -1,
            }}>
            {t.l}
          </button>
        ))}
      </div>

      {/* Filtros */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 8, marginBottom: 12 }}>
        <FiltroSelect label="Portal" value={filtroPortal} onChange={setFiltroPortal}
          opcoes={[{ v: "", l: "Todos" }, ...portais.map(p => ({ v: p.slug, l: p.nome }))]} />
        <FiltroSelect label="UF" value={filtroUF} onChange={setFiltroUF}
          opcoes={[{ v: "", l: "Todas" }, ...ufsDisponiveis.map(u => ({ v: u, l: u }))]} />
        <FiltroSelect label="Nível" value={filtroNivel} onChange={setFiltroNivel}
          opcoes={[{ v: "", l: "Todos" }, ...NIVEL_ORDEM.map(n => ({ v: n, l: NIVEIS[n].label }))]} />
        <FiltroSelect label="Status" value={filtroStatus} onChange={setFiltroStatus}
          opcoes={[
            { v: "todos", l: "Todos" }, { v: "em_sessao", l: "Em sessão" },
            { v: "agendado", l: "Agendado" }, { v: "suspenso", l: "Suspenso" },
            { v: "encerrado", l: "Encerrado" },
          ]} />
        <div style={{ gridColumn: "span 1" }}>
          <label style={{ fontSize: 10, color: "#5A5854", fontFamily: "monospace", letterSpacing: 0.6, textTransform: "uppercase", display: "block", marginBottom: 4 }}>Busca</label>
          <input value={busca} onChange={e => setBusca(e.target.value)} placeholder="n° / órgão / objeto"
            style={{ width: "100%", padding: "7px 10px", fontSize: 12, background: "#18181C", color: "#EEEEE8", border: "1px solid #2A2A32", borderRadius: 5, fontFamily: "monospace" }} />
        </div>
      </div>

      {/* Tabela densa */}
      <div style={{ background: "#0F0F12", border: "1px solid #2A2A32", borderRadius: 8, overflow: "hidden" }}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ background: "#18181C", borderBottom: "1px solid #2A2A32" }}>
                <th style={thStyle}></th>
                <th style={thStyle}>Portal</th>
                <th style={thStyle}>Órgão</th>
                <th style={thStyle}>Licitação</th>
                <th style={thStyle}>Nome Órgão</th>
                <th style={{ ...thStyle, textAlign: "center" }}>UF</th>
                <th style={{ ...thStyle, textAlign: "right" }}>Msgs</th>
                <th style={thStyle}>Última atualização</th>
                <th style={{ ...thStyle, textAlign: "center" }}>Ações</th>
              </tr>
            </thead>
            <tbody>
              {paginados.map(p => {
                const nivel = NIVEIS[p._nivel];
                const flashing = flashIds.has(p.id);
                const totMsgs = (p.snapshot?.mensagens || []).length || p.ultimos_eventos?.length || 0;
                const orgaoTxt = p.orgao || p.snapshot?.orgao || "—";
                return (
                  <tr key={p.id} style={{
                    borderBottom: "1px solid #1F1F25",
                    borderLeft: `3px solid ${nivel.cor}`,
                    animation: flashing ? "rowFlash 2.4s ease-out" : "none",
                    background: flashing ? "rgba(190,255,58,0.06)" : "transparent",
                    transition: "background 0.15s",
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = "#15151A"}
                  onMouseLeave={e => e.currentTarget.style.background = flashing ? "rgba(190,255,58,0.06)" : "transparent"}>
                    <td style={{ ...tdStyle, width: 30, paddingLeft: 8 }}>
                      <button onClick={() => toggleFavorito(p)}
                        title={p._favorito ? "Remover dos favoritos" : "Favoritar"}
                        style={{ background: "transparent", border: 0, cursor: "pointer", fontSize: 14, padding: 2, color: p._favorito ? "#FFB038" : "#3A3A44" }}>
                        {p._favorito ? "★" : "☆"}
                      </button>
                    </td>
                    <td style={tdStyle}>
                      <span style={{ fontSize: 10, fontFamily: "monospace", color: "#98968E", textTransform: "uppercase", letterSpacing: 0.5 }}>
                        {p.portal_slug || "—"}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <span style={{ fontFamily: "monospace", fontSize: 11, color: "#98968E" }}>
                        {p.identificador?.split("-")[0] || "—"}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <span style={{
                        display: "inline-block", padding: "3px 9px", borderRadius: 999,
                        background: nivel.bg, color: nivel.cor,
                        border: `1px solid ${nivel.cor}40`,
                        fontFamily: "monospace", fontSize: 11, fontWeight: 600,
                      }}>
                        {p.identificador || "—"}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#D5D4CE" }}>
                      {orgaoTxt}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "center", fontFamily: "monospace", fontSize: 11, color: "#98968E", fontWeight: 600 }}>
                      {p._uf}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "right" }}>
                      <button onClick={() => setPregaoChat(p)}
                        title={totMsgs > 0 ? "Ver mensagens" : "Sem mensagens — ver eventos"}
                        style={{ background: "transparent", border: 0, color: totMsgs > 0 ? nivel.cor : "#5A5854", cursor: "pointer", fontFamily: "monospace", fontSize: 11, fontWeight: 600, padding: "2px 6px" }}>
                        💬 {totMsgs}
                      </button>
                    </td>
                    <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 10, color: "#98968E" }}>
                      {fmtDataHora(p.snapshot?.atualizado_em || p.proxima_consulta_em || p.criado_em)}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "center", whiteSpace: "nowrap" }}>
                      <button onClick={() => {
                        const slug = p.portal_slug;
                        const parts = (p.identificador || "").split("-");
                        if (slug === "pncp" && parts.length >= 3) {
                          window.open(`https://pncp.gov.br/app/editais/${parts[0]}/${parts[1]}/${parts[2]}`, "_blank");
                        } else if (slug === "comprasnet" && parts.length >= 4) {
                          const [uasg, mod, num, ano] = parts;
                          const compraId = uasg.padStart(6, "0") + String(mod).padStart(2, "0") + num.padStart(5, "0") + ano;
                          window.open(`https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/landing?destino=acompanhamento-compra&compra=${compraId}`, "_blank");
                        }
                      }} title="Abrir no portal"
                        style={iconBtnStyle}>↗</button>
                      <button onClick={() => radarApi.silenciar(p.id, !p.silenciado).then(carregar)}
                        title={p.silenciado ? "Ativar" : "Silenciar"}
                        style={{ ...iconBtnStyle, color: p.silenciado ? "#FFB038" : "#98968E" }}>
                        {p.silenciado ? "🔇" : "🔔"}
                      </button>
                      <button onClick={() => { if (confirm(`Parar de monitorar ${p.identificador}?`)) radarApi.desmonitorar(p.id).then(carregar); }}
                        title="Desmonitorar"
                        style={{ ...iconBtnStyle, color: "#5A5854" }}>×</button>
                    </td>
                  </tr>
                );
              })}
              {paginados.length === 0 && (
                <tr>
                  <td colSpan={9} style={{ textAlign: "center", padding: 40, color: "#5A5854", fontSize: 12 }}>
                    {tab === "favoritas" ? "Nenhum pregão favoritado." :
                      (filtrados.length === 0
                        ? <>Nenhum pregão monitorado. Clique em <b style={{ color: "#BEFF3A" }}>+ MONITORAR</b></>
                        : "Nenhum resultado para essa página.")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <Paginacao
          total={filtrados.length}
          pagina={paginaAtual}
          totalPaginas={totalPaginas}
          pageSize={pageSize}
          inicio={inicioPag}
          fim={inicioPag + paginados.length}
          onMudarPagina={setPagina}
          onMudarPageSize={(s) => { setPageSize(s); setPagina(1); }}
        />
      </div>

      {feedAberto && (
        <EventFeed eventos={eventos}
          onMarcarLido={async (id) => {
            const agora = new Date().toISOString();
            setEventos(prev => prev.map(e => e.id === id ? { ...e, lido_em: agora } : e));
            try { await radarApi.marcarLido(id); } catch { setEventos(prev => prev.map(e => e.id === id ? { ...e, lido_em: null } : e)); }
          }}
          onMarcarTodosLidos={async () => {
            const agora = new Date().toISOString();
            setEventos(prev => prev.map(e => ({ ...e, lido_em: e.lido_em || agora })));
            try { await radarApi.marcarTodosLidos(); } catch {}
          }}
          onFechar={() => setFeedAberto(false)} />
      )}

      {showModal && (
        <ModalMonitorar portais={portais} onClose={() => setShowModal(false)} onSalvo={() => { setShowModal(false); carregar(); }} />
      )}

      {pregaoChat && (
        <ChatModal pregao={pregaoChat} onClose={() => setPregaoChat(null)} />
      )}
    </div>
  );
}

const thStyle = {
  textAlign: "left", padding: "10px 12px", fontFamily: "monospace", fontSize: 10,
  color: "#98968E", fontWeight: 700, letterSpacing: 0.8, textTransform: "uppercase",
  borderBottom: "1px solid #2A2A32",
};
const tdStyle = { padding: "10px 12px", color: "#EEEEE8", verticalAlign: "middle" };
const iconBtnStyle = {
  background: "transparent", border: 0, color: "#98968E", cursor: "pointer",
  padding: "2px 6px", fontSize: 14, marginLeft: 2,
};

function FiltroSelect({ label, value, onChange, opcoes }) {
  return (
    <div>
      <label style={{ fontSize: 10, color: "#5A5854", fontFamily: "monospace", letterSpacing: 0.6, textTransform: "uppercase", display: "block", marginBottom: 4 }}>{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)}
        style={{ width: "100%", padding: "7px 10px", fontSize: 12, background: "#18181C", color: "#EEEEE8", border: "1px solid #2A2A32", borderRadius: 5, fontFamily: "monospace" }}>
        {opcoes.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
      </select>
    </div>
  );
}

function Paginacao({ total, pagina, totalPaginas, pageSize, inicio, fim, onMudarPagina, onMudarPageSize }) {
  // Gerar até 5 botões de página com elipse
  const paginas = [];
  if (totalPaginas <= 7) {
    for (let i = 1; i <= totalPaginas; i++) paginas.push(i);
  } else {
    paginas.push(1);
    if (pagina > 3) paginas.push("…");
    for (let i = Math.max(2, pagina - 1); i <= Math.min(totalPaginas - 1, pagina + 1); i++) paginas.push(i);
    if (pagina < totalPaginas - 2) paginas.push("…");
    paginas.push(totalPaginas);
  }

  return (
    <div style={{ padding: "10px 14px", borderTop: "1px solid #1F1F25", display: "flex", justifyContent: "space-between", alignItems: "center", background: "#0A0A0D", flexWrap: "wrap", gap: 10 }}>
      <span style={{ fontSize: 11, fontFamily: "monospace", color: "#98968E" }}>
        {total > 0 ? <>Mostrando <b style={{ color: "#EEEEE8" }}>{inicio + 1}-{fim}</b> de <b style={{ color: "#EEEEE8" }}>{total}</b></> : "Nenhum resultado"}
      </span>

      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <button onClick={() => onMudarPagina(Math.max(1, pagina - 1))} disabled={pagina <= 1}
          style={pagBtnStyle(false, pagina <= 1)}>‹</button>
        {paginas.map((p, i) => (
          p === "…"
            ? <span key={`e${i}`} style={{ color: "#5A5854", padding: "0 4px", fontFamily: "monospace", fontSize: 11 }}>…</span>
            : <button key={p} onClick={() => onMudarPagina(p)} style={pagBtnStyle(p === pagina)}>{p}</button>
        ))}
        <button onClick={() => onMudarPagina(Math.min(totalPaginas, pagina + 1))} disabled={pagina >= totalPaginas}
          style={pagBtnStyle(false, pagina >= totalPaginas)}>›</button>
      </div>

      <select value={pageSize} onChange={e => onMudarPageSize(Number(e.target.value))}
        style={{ padding: "4px 8px", fontSize: 11, background: "#18181C", color: "#98968E", border: "1px solid #2A2A32", borderRadius: 4, fontFamily: "monospace" }}>
        {PAGE_SIZES.map(s => <option key={s} value={s}>Exibir {s}</option>)}
      </select>
    </div>
  );
}

const pagBtnStyle = (ativo, disabled) => ({
  minWidth: 26, height: 26, padding: "0 8px",
  background: ativo ? "#BEFF3A" : "transparent",
  color: ativo ? "#1A1A18" : (disabled ? "#3A3A44" : "#98968E"),
  border: ativo ? "1px solid #BEFF3A" : "1px solid #2A2A32",
  borderRadius: 4, cursor: disabled ? "default" : "pointer",
  fontSize: 11, fontFamily: "monospace", fontWeight: 700,
});

// ── Modal Monitorar (preservado do arquivo anterior) ──────────────────
const MODALIDADES_COMPRASNET = [
  { cod: "0", nome: "Detectar automaticamente" },
  { cod: "5", nome: "Pregão Eletrônico" },
  { cod: "6", nome: "Dispensa Eletrônica" },
  { cod: "3", nome: "Concorrência" },
  { cod: "4", nome: "Pregão Presencial" },
  { cod: "20", nome: "RDC Eletrônico" },
  { cod: "7", nome: "Inexigibilidade" },
];

function parsearURL(input) {
  if (!input) return null;
  const s = input.trim();
  const mPncp = s.match(/pncp\.gov\.br\/app\/editais\/(\d{14})\/(\d{4})\/(\d+)/i);
  if (mPncp) return { portal_slug: "pncp", identificador: `${mPncp[1]}-${mPncp[2]}-${mPncp[3]}` };
  const mCompra = s.match(/compra=(\d{17})/i);
  if (mCompra) {
    const c = mCompra[1];
    const uasg = c.slice(0, 6), mod = c.slice(6, 8).replace(/^0/, ""), num = c.slice(8, 13), ano = c.slice(13);
    return { portal_slug: "comprasnet", identificador: `${uasg}-${mod}-${num}-${ano}` };
  }
  const mAspUasg = s.match(/uasg=(\d{4,6})/i);
  const mAspNum = s.match(/num[a-z]*=(\d{4,6})/i);
  const mAspAno = s.match(/ano[a-z]*=(\d{4})/i);
  if (mAspUasg && mAspNum) {
    return { portal_slug: "comprasnet", identificador: `${mAspUasg[1]}-${String(mAspNum[1]).padStart(5, "0")}-${mAspAno ? mAspAno[1] : new Date().getFullYear()}` };
  }
  const limpo = s.replace(/\s+/g, "");
  if (/^\d{14}-\d{4}-\d+$/.test(limpo)) return { portal_slug: "pncp", identificador: limpo };
  if (/^\d{4,6}-\d{1,2}-\d{1,5}-\d{4}$/.test(limpo) || /^\d{4,6}-\d{1,5}-\d{4}$/.test(limpo)) return { portal_slug: "comprasnet", identificador: limpo };
  return null;
}

function ModalMonitorar({ portais, onClose, onSalvo }) {
  const [colaUrl, setColaUrl] = useState("");
  const [parsed, setParsed] = useState(null);
  const [parseErro, setParseErro] = useState("");
  const [modoManual, setModoManual] = useState(false);
  const [portal, setPortal] = useState("comprasnet");
  const [uasg, setUasg] = useState("");
  const [modalidade, setModalidade] = useState("0");
  const [numero, setNumero] = useState("");
  const [ano, setAno] = useState(String(new Date().getFullYear()));
  const [pollSes, setPollSes] = useState(30);
  const [pollIdle, setPollIdle] = useState(300);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => {
    const p = parsearURL(colaUrl);
    setParsed(p);
    setParseErro(colaUrl && !p ? "Formato não reconhecido — cole URL do PNCP/ComprasGov ou use modo manual" : "");
  }, [colaUrl]);

  const numeroPad = numero ? String(numero).padStart(5, "0") : "";
  const idManual = uasg && numero && ano
    ? (modalidade === "0" ? `${uasg.trim()}-${numeroPad}-${ano}` : `${uasg.trim()}-${modalidade}-${numeroPad}-${ano}`)
    : "";

  const idFinal = modoManual ? idManual : (parsed?.identificador || "");
  const portalFinal = modoManual ? portal : (parsed?.portal_slug || "");

  const salvar = async () => {
    if (!idFinal || !portalFinal) return setErro("Cole a URL do pregão ou preencha o modo manual");
    setSalvando(true); setErro("");
    try {
      await radarApi.monitorar({
        portal_slug: portalFinal, identificador: idFinal,
        polling_seg_sessao: Number(pollSes), polling_seg_idle: Number(pollIdle),
      });
      onSalvo();
    } catch (e) { setErro(e.message); }
    setSalvando(false);
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200 }}>
      <div style={{ background: "#FFF", color: "#1A1A18", padding: 24, borderRadius: 12, width: 520, maxWidth: "90vw" }}>
        <h3 style={{ margin: "0 0 4px", fontSize: 16, fontWeight: 700 }}>Monitorar pregão</h3>
        <p style={{ margin: "0 0 16px", fontSize: 12, color: "#6B7280" }}>Cole a URL do pregão (PNCP ou Compras.gov.br) ou use o modo manual.</p>

        {!modoManual && (
          <>
            <label style={{ fontSize: 11, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>URL do pregão</label>
            <textarea value={colaUrl} onChange={e => setColaUrl(e.target.value)}
              placeholder="Ex: https://pncp.gov.br/app/editais/39485396000140/2026/9"
              style={{ width: "100%", padding: "10px 12px", fontSize: 12, marginBottom: 8, border: "1px solid #D1D5DB", borderRadius: 6, fontFamily: "monospace", minHeight: 60, resize: "vertical" }} />
            {parsed && (
              <div style={{ background: "linear-gradient(180deg,#eef7ff 0%,#f8fbff 100%)", border: "1px solid #2684FF", borderRadius: 8, padding: 12, marginBottom: 12 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: "#2684FF", textTransform: "uppercase", letterSpacing: 0.5 }}>
                  ✓ {parsed.portal_slug === "pncp" ? "PNCP" : "Compras.gov.br"}
                </span>
                <div style={{ fontFamily: "monospace", fontSize: 12, color: "#1f374a", marginTop: 4 }}>
                  ID: <b>{parsed.identificador}</b>
                </div>
              </div>
            )}
            {parseErro && <div style={{ color: "#DC2626", fontSize: 11, marginBottom: 12 }}>{parseErro}</div>}
            <button onClick={() => setModoManual(true)}
              style={{ background: "transparent", border: 0, color: "#2684FF", fontSize: 11, cursor: "pointer", padding: 0, marginBottom: 12, textDecoration: "underline" }}>
              ou preencher manualmente
            </button>
          </>
        )}

        {modoManual && (
          <>
            <div style={{ marginBottom: 12 }}>
              <button onClick={() => setModoManual(false)}
                style={{ background: "transparent", border: 0, color: "#2684FF", fontSize: 11, cursor: "pointer", padding: 0, textDecoration: "underline" }}>
                ← voltar pra colar URL
              </button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1.4fr", gap: 8, marginBottom: 10 }}>
              <Field label="UASG"><input value={uasg} onChange={e => setUasg(e.target.value.replace(/\D/g, ""))} placeholder="160471" inputMode="numeric" style={modalInput} /></Field>
              <Field label="Modalidade">
                <select value={modalidade} onChange={e => setModalidade(e.target.value)} style={modalInput}>
                  {MODALIDADES_COMPRASNET.map(m => <option key={m.cod} value={m.cod}>{m.cod === "0" ? m.nome : `${m.cod} — ${m.nome}`}</option>)}
                </select>
              </Field>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 8 }}>
              <Field label="Número"><input value={numero} onChange={e => setNumero(e.target.value.replace(/\D/g, ""))} placeholder="67" inputMode="numeric" style={modalInput} /></Field>
              <Field label="Ano"><input value={ano} onChange={e => setAno(e.target.value.replace(/\D/g, "").slice(0, 4))} placeholder="2026" inputMode="numeric" style={modalInput} /></Field>
            </div>
            <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 12, fontFamily: "monospace" }}>
              ID: {idManual || <span style={{ color: "#9CA3AF" }}>UASG-MOD-NUM-ANO</span>}
            </div>
          </>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 16 }}>
          <Field label="Polling sessão (s)"><input type="number" value={pollSes} onChange={e => setPollSes(e.target.value)} style={modalInput} /></Field>
          <Field label="Polling idle (s)"><input type="number" value={pollIdle} onChange={e => setPollIdle(e.target.value)} style={modalInput} /></Field>
        </div>

        {erro && <div style={{ color: "#DC2626", fontSize: 12, marginBottom: 10 }}>{erro}</div>}

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button onClick={onClose} style={{ padding: "8px 16px", background: "#F3F4F6", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12 }}>Cancelar</button>
          <button onClick={salvar} disabled={salvando || !idFinal}
            style={{ padding: "8px 16px", background: idFinal ? "#1A1A18" : "#9CA3AF", color: "#FFF", border: "none", borderRadius: 6, cursor: idFinal ? "pointer" : "not-allowed", fontSize: 12, fontWeight: 600 }}>
            {salvando ? "Salvando…" : "Monitorar"}
          </button>
        </div>
      </div>
    </div>
  );
}

const modalInput = { width: "100%", padding: "8px 10px", fontSize: 13, border: "1px solid #D1D5DB", borderRadius: 6, fontFamily: "monospace" };
function Field({ label, children }) {
  return (
    <div>
      <label style={{ fontSize: 11, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>{label}</label>
      {children}
    </div>
  );
}
