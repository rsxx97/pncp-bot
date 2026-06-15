const COR_POS = (pos) => {
  if (!pos) return "#6B7280";
  if (pos === 1) return "#16A34A";
  if (pos <= 3) return "#FFB038";
  return "#DC2626";
};

const COR_STATUS = {
  em_sessao: "#16A34A",
  agendado: "#5A9EF7",
  suspenso: "#FFB038",
  encerrado: "#6B7280",
  fracassado: "#DC2626",
  deserto: "#DC2626",
};

const STATUS_LABEL = {
  em_sessao: "🟢 EM SESSÃO",
  agendado: "🕐 AGENDADO",
  suspenso: "⏸ SUSPENSO",
  encerrado: "⚫ ENCERRADO",
  fracassado: "❌ FRACASSADO",
  deserto: "❌ DESERTO",
};

const FASE_LABEL = {
  propostas: "Recebendo propostas",
  lances: "Disputa de lances",
  negociacao: "Negociação",
  habilitacao: "Habilitação",
  adjudicacao: "Adjudicação",
  homologacao: "Homologação",
};

const BRL = (v) => {
  if (v == null) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
};

const fmtData = (iso) => {
  if (!iso) return null;
  try { return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }); }
  catch { return null; }
};

const fmtDataHora = (iso) => {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch { return null; }
};

const tempoRelativo = (iso, futuro = false) => {
  if (!iso) return null;
  const d = new Date(iso).getTime();
  const diff = futuro ? d - Date.now() : Date.now() - d;
  if (diff < 0) return null;
  const min = Math.floor(diff / 60000);
  if (min < 60) return `${min}min`;
  const h = Math.floor(min / 60);
  if (h < 48) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
};

export default function PregaoCard({ pregao, onSilenciar, onAbrir, onDesmonitorar, onVerChat, flashing }) {
  const s = pregao.snapshot || {};
  const status = pregao.status || "agendado";
  const fase = pregao.fase || s.fase;
  const pos = s.minha_posicao;
  const valorEst = s.valor_estimado;
  const abertura = s.data_abertura;
  const encerramento = s.data_encerramento;
  const temDadosLive = pos != null || s.melhor_lance != null || (s.lances && s.lances.length > 0);

  // Tempo até abertura/encerramento
  const agora = Date.now();
  const temAberturaFutura = abertura && new Date(abertura).getTime() > agora;
  const temEncerramentoFuturo = encerramento && new Date(encerramento).getTime() > agora;

  return (
    <div style={{
      background: "#FFF", borderRadius: 12, padding: 14,
      border: `1px solid ${flashing ? "#BEFF3A" : "#E5E7EB"}`,
      boxShadow: flashing ? "0 0 16px rgba(190,255,58,0.4)" : "none",
      transition: "box-shadow 0.3s, border-color 0.3s",
      display: "flex", flexDirection: "column", gap: 8,
    }}>
      {/* Header: portal + número + status */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, flex: 1 }}>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <span style={{ fontSize: 9, padding: "2px 6px", background: "#1A1A18", color: "#FFF", borderRadius: 4, fontWeight: 700, fontFamily: "monospace" }}>
              {pregao.portal_slug?.toUpperCase()}
            </span>
            <span style={{ fontSize: 12, fontWeight: 700, color: "#1A1A18", fontFamily: "monospace" }}>{pregao.identificador}</span>
          </div>
          <div style={{ fontSize: 11, color: "#6B7280", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {pregao.orgao || s.orgao || "—"}
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: COR_STATUS[status] || "#6B7280", fontFamily: "monospace" }}>
            {STATUS_LABEL[status] || status}
          </span>
          {fase && (
            <span style={{ fontSize: 9, padding: "1px 6px", background: "#F3F4F6", color: "#374151", borderRadius: 4, fontWeight: 600 }}>
              {FASE_LABEL[fase] || fase}
            </span>
          )}
        </div>
      </div>

      {/* Objeto */}
      <div style={{ fontSize: 12, color: "#374151", overflow: "hidden", textOverflow: "ellipsis", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
        {pregao.objeto || s.objeto || "—"}
      </div>

      {/* Linha de info: abertura, encerramento, valor */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, fontSize: 10, color: "#6B7280" }}>
        {abertura && (
          <div>
            <div style={{ fontSize: 9, color: "#9CA3AF", fontWeight: 600, textTransform: "uppercase" }}>Abertura</div>
            <div style={{ fontSize: 11, color: "#1A1A18", fontWeight: 600 }}>
              {fmtData(abertura)}
              {temAberturaFutura && (
                <span style={{ color: "#5A9EF7", marginLeft: 4 }}>em {tempoRelativo(abertura, true)}</span>
              )}
            </div>
          </div>
        )}
        {encerramento && (
          <div>
            <div style={{ fontSize: 9, color: "#9CA3AF", fontWeight: 600, textTransform: "uppercase" }}>Encerra</div>
            <div style={{ fontSize: 11, color: "#1A1A18", fontWeight: 600 }}>
              {fmtData(encerramento)}
              {temEncerramentoFuturo && (
                <span style={{ color: "#FFB038", marginLeft: 4 }}>em {tempoRelativo(encerramento, true)}</span>
              )}
            </div>
          </div>
        )}
        {valorEst != null && (
          <div>
            <div style={{ fontSize: 9, color: "#9CA3AF", fontWeight: 600, textTransform: "uppercase" }}>Valor estimado</div>
            <div style={{ fontSize: 11, color: "#1A1A18", fontWeight: 700 }}>{BRL(valorEst)}</div>
          </div>
        )}
      </div>

      {/* Posição + lances (só mostra se tem dado live) */}
      {temDadosLive && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, padding: "8px 0", borderTop: "1px solid #F3F4F6" }}>
          <div>
            <div style={{ fontSize: 9, color: "#9CA3AF", fontWeight: 600, textTransform: "uppercase" }}>Posição</div>
            <div style={{ fontSize: 16, fontWeight: 800, color: COR_POS(pos) }}>{pos ? `${pos}º` : "—"}</div>
          </div>
          <div>
            <div style={{ fontSize: 9, color: "#9CA3AF", fontWeight: 600, textTransform: "uppercase" }}>Meu lance</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#1A1A18" }}>{BRL(s.meu_melhor_lance)}</div>
          </div>
          <div>
            <div style={{ fontSize: 9, color: "#9CA3AF", fontWeight: 600, textTransform: "uppercase" }}>Melhor geral</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#1A1A18" }}>{BRL(s.melhor_lance)}</div>
          </div>
        </div>
      )}

      {/* ÚLTIMA MENSAGEM DO PREGOEIRO — destaque visível */}
      {(() => {
        const msgs = s.mensagens || [];
        if (msgs.length === 0) return null;
        // Pega última mensagem do pregoeiro (ordenada do mais novo pro mais velho)
        const ultimaMsgPregoeiro = msgs.find(m => m.remetente === "pregoeiro");
        if (!ultimaMsgPregoeiro) return null;
        const cat = ultimaMsgPregoeiro.categoria_label || "";
        const urgente = cat === "convocacao_documentacao" || cat === "pedido_diligencia";
        const cor = urgente ? "#DC2626" : "#5A9EF7";
        const bgCor = urgente ? "#FEF2F2" : "#EFF6FF";
        return (
          <div onClick={onVerChat} style={{
            borderTop: "1px solid #F3F4F6", paddingTop: 8, marginTop: 4,
            background: bgCor, padding: "10px 12px", borderRadius: 8, borderLeft: `3px solid ${cor}`,
            cursor: "pointer", transition: "background 0.15s",
          }}
            onMouseEnter={e => e.currentTarget.style.filter = "brightness(0.96)"}
            onMouseLeave={e => e.currentTarget.style.filter = "none"}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <span style={{ fontSize: 14 }}>{urgente ? "🚨" : "💬"}</span>
              <span style={{ fontSize: 9, fontWeight: 700, color: cor, textTransform: "uppercase", letterSpacing: 0.5 }}>
                {urgente ? "PREGOEIRO — RESPONDER" : "Mensagem do pregoeiro"}
              </span>
              <span style={{ fontSize: 9, color: "#9CA3AF", marginLeft: "auto", fontFamily: "monospace" }}>
                {ultimaMsgPregoeiro.horario ? new Date(ultimaMsgPregoeiro.horario.replace(" ", "T")).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : ""}
              </span>
            </div>
            <div style={{ fontSize: 12, color: "#1A1A18", lineHeight: 1.4, display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
              {ultimaMsgPregoeiro.texto}
            </div>
            {msgs.length > 1 && (
              <div style={{ marginTop: 6, fontSize: 10, color: cor, fontWeight: 700 }}>
                Ver chat completo ({msgs.length} mensagens) ›
              </div>
            )}
          </div>
        );
      })()}

      {/* Eventos recentes (debug minor) */}
      {pregao.ultimos_eventos?.length > 0 && !(s.mensagens || []).length && (
        <div style={{ borderTop: "1px solid #F3F4F6", paddingTop: 6, display: "flex", flexDirection: "column", gap: 3 }}>
          {pregao.ultimos_eventos.slice(0, 3).map(e => (
            <div key={e.id} style={{ fontSize: 10, color: "#6B7280" }}>
              <span style={{ fontFamily: "monospace", fontWeight: 600 }}>{e.tipo}</span>
              {" · "}{e.titulo}
            </div>
          ))}
        </div>
      )}

      {/* Ações */}
      <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
        {(s.mensagens || []).length > 0 && (
          <button onClick={onVerChat}
            style={{ flex: 1, padding: "5px 8px", fontSize: 10, background: "#1A1A18", color: "#FFF", border: "none", borderRadius: 5, fontWeight: 600, cursor: "pointer" }}>
            💬 Chat ({(s.mensagens || []).length})
          </button>
        )}
        <button onClick={onAbrir}
          style={{ flex: 1, padding: "5px 8px", fontSize: 10, background: "#F3F4F6", border: "none", borderRadius: 5, fontWeight: 600, cursor: "pointer" }}>
          Abrir no portal
        </button>
        <button onClick={onSilenciar}
          style={{ flex: 1, padding: "5px 8px", fontSize: 10, background: pregao.silenciado ? "#FEF3C7" : "#F3F4F6", border: "none", borderRadius: 5, fontWeight: 600, cursor: "pointer" }}>
          {pregao.silenciado ? "Ativar" : "Silenciar"}
        </button>
        <button onClick={onDesmonitorar}
          style={{ padding: "5px 8px", fontSize: 10, background: "#FEF2F2", color: "#DC2626", border: "none", borderRadius: 5, fontWeight: 600, cursor: "pointer" }}>
          ✕
        </button>
      </div>
    </div>
  );
}
