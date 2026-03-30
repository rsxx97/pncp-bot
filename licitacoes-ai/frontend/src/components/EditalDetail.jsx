import { useState, useEffect } from "react";
import ScoreBadge from "./ScoreBadge";
import StatusBadge from "./StatusBadge";
import ActionBtn from "./ActionButton";
import { api } from "../api";

function formatBRL(v) {
  if (v == null || v === 0) return "N/I";
  if (v >= 1e6) return `R$ ${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `R$ ${(v / 1e3).toFixed(0)}K`;
  return `R$ ${v.toFixed(0)}`;
}

function ArquivosSection({ pncpId }) {
  const [arquivos, setArquivos] = useState(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  const carregar = async () => {
    if (arquivos) { setOpen(!open); return; }
    setLoading(true);
    try {
      const data = await api.listarArquivos(pncpId);
      setArquivos(data);
      setOpen(true);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const allFiles = [
    ...(arquivos?.local || []),
    ...(arquivos?.pncp || []).map((f, i) => ({ ...f, remote: true, downloadUrl: `/api/editais/${pncpId}/pdf/download_arquivo/${i}` })),
  ];

  const getIcon = (titulo) => {
    const t = (titulo || "").toLowerCase();
    if (t.includes("termo") || t.includes("tr")) return "📄";
    if (t.includes("planilha") || t.includes("xlsx") || t.includes("custo")) return "📊";
    if (t.includes("edital")) return "📋";
    if (t.includes("ata") || t.includes("contrato")) return "📝";
    return "📎";
  };

  return (
    <div style={{ marginBottom: 20 }}>
      <button onClick={carregar}
        style={{ background: "none", border: "1px solid #2A2A32", borderRadius: 8, padding: "8px 16px", cursor: "pointer", fontSize: 13, fontWeight: 600, color: "#EEEEE8", display: "flex", alignItems: "center", gap: 6 }}>
        📁 Documentos do edital {loading ? "(carregando...)" : open ? "▲" : "▼"}
      </button>
      {open && arquivos && (
        <div style={{ marginTop: 10, border: "1px solid #2A2A32", borderRadius: 10, overflow: "hidden", background: "#111114" }}>
          {allFiles.length === 0 ? (
            <div style={{ padding: 16, textAlign: "center", color: "#5A5854", fontSize: 13 }}>Nenhum documento encontrado no PNCP</div>
          ) : (
            allFiles.map((f, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", borderBottom: i < allFiles.length - 1 ? "1px solid rgba(255,255,255,0.03)" : "none" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, minWidth: 0 }}>
                  <span style={{ fontSize: 16 }}>{getIcon(f.titulo)}</span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: "#EEEEE8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.titulo || "Arquivo"}</div>
                    {f.tamanho_kb && <div style={{ fontSize: 11, color: "#5A5854" }}>{f.tamanho_kb} KB</div>}
                  </div>
                </div>
                <button onClick={() => window.open(f.downloadUrl || f.url, '_blank')}
                  style={{ background: "#222228", border: "1px solid #2A2A32", borderRadius: 6, padding: "5px 12px", cursor: "pointer", fontSize: 12, fontWeight: 600, color: "#EEEEE8", whiteSpace: "nowrap" }}>
                  Baixar
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function UploadPlanilha({ pncpId, onUploaded }) {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setResult(null);
    try {
      const res = await api.uploadPlanilha(pncpId, file);
      setResult({ ok: true, name: res.filename, size: res.size_kb });
      onUploaded?.();
    } catch (err) {
      setResult({ ok: false, msg: err.message });
    }
    setUploading(false);
    e.target.value = "";
  };

  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{
        display: "inline-flex", alignItems: "center", gap: 8, padding: "8px 16px",
        background: "#111114", border: "1px solid #2A2A32", borderRadius: 8,
        cursor: uploading ? "wait" : "pointer", fontSize: 13, fontWeight: 600, color: "#EEEEE8",
      }}>
        <span>📊</span>
        <span>{uploading ? "Enviando..." : "Enviar minha planilha"}</span>
        <input type="file" accept=".xlsx,.xls,.ods" onChange={handleFile} style={{ display: "none" }} disabled={uploading} />
      </label>
      {result && (
        <div style={{ marginTop: 6, fontSize: 12, color: result.ok ? "#2EDDA8" : "#FF4D4D" }}>
          {result.ok ? `Planilha "${result.name}" (${result.size}KB) salva com sucesso` : `Erro: ${result.msg}`}
        </div>
      )}
    </div>
  );
}

function PostosManualForm({ pncpId, onSaved }) {
  const [postos, setPostos] = useState([{ funcao: "", quantidade: 1, jornada: "44h" }]);
  const [saving, setSaving] = useState(false);

  const addPosto = () => setPostos([...postos, { funcao: "", quantidade: 1, jornada: "44h" }]);
  const removePosto = (i) => setPostos(postos.filter((_, idx) => idx !== i));
  const updatePosto = (i, field, val) => {
    const copy = [...postos];
    copy[i] = { ...copy[i], [field]: val };
    setPostos(copy);
  };

  const salvar = async () => {
    const validos = postos.filter(p => p.funcao.trim());
    if (!validos.length) return;
    setSaving(true);
    try {
      await api.adicionarPostoManual(pncpId, validos);
      onSaved?.();
    } catch (e) { console.error(e); }
    setSaving(false);
  };

  const inputStyle = { padding: "6px 8px", border: "1px solid #DDD", borderRadius: 6, fontSize: 13 };

  return (
    <div style={{ background: "#FFFDF0", borderRadius: 10, padding: 14, border: "1px solid #FDE68A", marginBottom: 16 }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: "#92400E", marginBottom: 8 }}>Adicionar mao de obra manualmente</div>
      {postos.map((p, i) => (
        <div key={i} style={{ display: "flex", gap: 6, marginBottom: 6, alignItems: "center" }}>
          <input placeholder="Funcao (ex: Copeira)" value={p.funcao} onChange={e => updatePosto(i, "funcao", e.target.value)}
            style={{ ...inputStyle, flex: 2 }} />
          <input type="number" min={1} value={p.quantidade} onChange={e => updatePosto(i, "quantidade", parseInt(e.target.value) || 1)}
            style={{ ...inputStyle, width: 50 }} />
          <select value={p.jornada} onChange={e => updatePosto(i, "jornada", e.target.value)}
            style={{ ...inputStyle, width: 70 }}>
            <option value="44h">44h</option>
            <option value="40h">40h</option>
            <option value="36h">36h</option>
            <option value="30h">30h</option>
            <option value="12x36">12x36</option>
          </select>
          {postos.length > 1 && <button onClick={() => removePosto(i)} style={{ background: "none", border: "none", color: "#DC2626", cursor: "pointer", fontSize: 16 }}>x</button>}
        </div>
      ))}
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button onClick={addPosto} style={{ background: "#FEF3C7", border: "1px solid #FDE68A", borderRadius: 6, padding: "4px 10px", fontSize: 12, cursor: "pointer" }}>+ Posto</button>
        <button onClick={salvar} disabled={saving} style={{ background: "#F59E0B", color: "#FFF", border: "none", borderRadius: 6, padding: "4px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
          {saving ? "Salvando..." : "Salvar postos"}
        </button>
      </div>
    </div>
  );
}

function ProcessingBanner({ status, startedAt }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (status !== "analisando" && status !== "precificando") return;
    const t0 = startedAt || Date.now();
    const tick = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 1000);
    return () => clearInterval(tick);
  }, [status, startedAt]);

  if (status !== "analisando" && status !== "precificando") return null;

  const isAnalise = status === "analisando";
  const bg = isAnalise ? "#EDE9FE" : "#FEF3C7";
  const color = isAnalise ? "#5B21B6" : "#92400E";
  const border = isAnalise ? "#C4B5FD" : "#FDE68A";

  const steps = isAnalise
    ? [
        { label: "Baixando edital, TR e anexos do PNCP", t: 0 },
        { label: "Analisando edital (requisitos e habilitacao)", t: 15 },
        { label: "Analisando TR (postos, CCT, beneficios)", t: 40 },
        { label: "Avaliando viabilidade e ranking de empresas", t: 80 },
      ]
    : [
        { label: "Carregando dados do edital e TR", t: 0 },
        { label: "Identificando CCT e calculando encargos", t: 10 },
        { label: "Montando planilha de custos por cargo", t: 30 },
        { label: "Simulando cenarios de lance e break-even", t: 60 },
      ];

  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  const timeStr = min > 0 ? `${min}m ${sec.toString().padStart(2, "0")}s` : `${sec}s`;
  const pct = Math.min((elapsed / 300) * 100, 100);

  return (
    <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 10, padding: 16, marginBottom: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <svg width="24" height="24" viewBox="0 0 24 24" style={{ animation: "spin 1s linear infinite", flexShrink: 0 }}>
          <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
          <circle cx="12" cy="12" r="10" stroke={color} strokeWidth="2.5" fill="none" strokeDasharray="31 31" strokeLinecap="round" />
        </svg>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color }}>{isAnalise ? "Analisando edital..." : "Gerando planilha..."}</div>
        </div>
        <div style={{ fontSize: 13, fontWeight: 600, color, fontVariantNumeric: "tabular-nums" }}>{timeStr}</div>
      </div>
      {/* Progress bar */}
      <div style={{ background: `${color}22`, borderRadius: 4, height: 4, marginBottom: 12 }}>
        <div style={{ background: color, height: 4, borderRadius: 4, width: `${pct}%`, transition: "width 1s linear" }} />
      </div>
      {/* Steps */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {steps.map((step, i) => {
          const active = elapsed >= step.t && (i === steps.length - 1 || elapsed < steps[i + 1].t);
          const done = i < steps.length - 1 ? elapsed >= steps[i + 1].t : false;
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: done ? color : active ? color : `${color}88` }}>
              <span style={{ width: 16, textAlign: "center", fontSize: 13 }}>{done ? "\u2713" : active ? "\u25CF" : "\u25CB"}</span>
              <span style={{ fontWeight: active ? 600 : 400 }}>{step.label}</span>
            </div>
          );
        })}
      </div>
      {elapsed > 240 && <div style={{ fontSize: 11, color, opacity: 0.6, marginTop: 8, textAlign: "center" }}>Tempo limite: 5 min. Se travar, o status volta para permitir retry.</div>}
    </div>
  );
}

function ErrorBanner({ status, onRetry }) {
  if (status !== "erro_analise" && status !== "erro_precificacao") return null;
  const isAnalise = status === "erro_analise";
  return (
    <div style={{ background: "#FEF2F2", border: "1px solid #FEE2E2", borderRadius: 10, padding: 16, marginBottom: 20, textAlign: "center" }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: "#991B1B", marginBottom: 4 }}>
        {isAnalise ? "Erro na analise" : "Erro na precificacao"}
      </div>
      <div style={{ fontSize: 12, color: "#7F1D1D", marginBottom: 10 }}>
        O processamento falhou ou excedeu o tempo limite de 5 minutos.
      </div>
      <button onClick={onRetry} style={{ background: "#DC2626", color: "#FFF", border: "none", borderRadius: 6, padding: "6px 16px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
        Tentar novamente
      </button>
    </div>
  );
}

export default function EditalDetailPanel({ pncpId, onClose, onRefresh }) {
  const [edital, setEdital] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showPostosForm, setShowPostosForm] = useState(false);
  const [processingStarted, setProcessingStarted] = useState(null);

  useEffect(() => {
    if (!pncpId) return;
    setLoading(true);
    api.getEdital(pncpId)
      .then(setEdital)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [pncpId]);

  if (!pncpId) return null;

  const handleAction = async (action) => {
    try {
      if (action === "analisar") {
        setEdital(prev => ({ ...prev, status: "analisando" }));
        setProcessingStarted(Date.now());
        await api.analisar(pncpId);
      } else if (action === "planilha") {
        setEdital(prev => ({ ...prev, status: "precificando" }));
        setProcessingStarted(Date.now());
        await api.gerarPlanilha(pncpId);
      } else if (action === "competitivo") {
        await api.competitivo(pncpId);
      } else if (action === "arquivar") {
        await api.arquivar(pncpId); onClose(); onRefresh?.(); return;
      }
      startPolling();
    } catch (e) { console.error(e); }
  };

  const startPolling = () => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const fresh = await api.getEdital(pncpId);
        setEdital(fresh);
        const processing = fresh.status === "analisando" || fresh.status === "precificando";
        if (!processing || attempts > 65) {
          clearInterval(interval);
          setProcessingStarted(null);
          onRefresh?.();
        }
      } catch (e) {
        console.error("Polling error:", e);
      }
    }, 5000);
  };

  const status = edital?.status || "";

  return (
    <>
      <div onClick={onClose} style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.2)", zIndex: 999 }} />
      <div style={{ position: "fixed", top: 0, right: 0, bottom: 0, width: 420, background: "#FFFFFF", boxShadow: "-4px 0 24px rgba(0,0,0,0.08)", zIndex: 1000, display: "flex", flexDirection: "column", borderLeft: "1px solid #E8E8E4" }}>
        {/* Header */}
        <div style={{ padding: "24px 24px 16px", borderBottom: "1px solid #F0F0EC", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div style={{ flex: 1 }}>
            {loading ? <div style={{ color: "#AEAEA8" }}>Carregando...</div> : (
              <>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
                  <ScoreBadge score={edital?.score_relevancia} />
                  <StatusBadge status={status} />
                </div>
                <div style={{ fontSize: 17, fontWeight: 600, color: "#1A1A18", lineHeight: 1.3 }}>{edital?.objeto}</div>
                <div style={{ fontSize: 13, color: "#8A8A85", marginTop: 6 }}>{edital?.orgao_nome} — Abertura: {edital?.data_abertura || "N/I"}</div>
              </>
            )}
          </div>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <button onClick={async () => { setLoading(true); try { const fresh = await api.getEdital(pncpId); setEdital(fresh); } catch(e){} setLoading(false); }}
              style={{ background: "#F0F0EC", border: "none", borderRadius: 6, padding: "4px 10px", cursor: "pointer", fontSize: 12, fontWeight: 600, color: "#5A5A56" }}
              title="Atualizar dados">↻</button>
            <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 22, cursor: "pointer", color: "#AEAEA8", padding: 4 }}>x</button>
          </div>
        </div>

        {/* Body */}
        {edital && (
          <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
            {/* Stats grid */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 24 }}>
              <div style={{ background: "#F8F8F6", borderRadius: 8, padding: 14 }}>
                <div style={{ fontSize: 12, color: "#8A8A85" }}>Valor estimado</div>
                <div style={{ fontSize: 20, fontWeight: 600, color: "#1A1A18" }}>{formatBRL(edital.valor_estimado)}</div>
              </div>
              <div style={{ background: "#F8F8F6", borderRadius: 8, padding: 14 }}>
                <div style={{ fontSize: 12, color: "#8A8A85" }}>Empresa sugerida</div>
                <div style={{ fontSize: 20, fontWeight: 600, color: "#1A1A18" }}>{edital.empresa_sugerida || "—"}</div>
              </div>
              {edital.margem_percentual != null && (
                <div style={{ background: "#F8F8F6", borderRadius: 8, padding: 14 }}>
                  <div style={{ fontSize: 12, color: "#8A8A85" }}>Margem</div>
                  <div style={{ fontSize: 20, fontWeight: 600, color: "#065F46" }}>{edital.margem_percentual?.toFixed(1)}%</div>
                </div>
              )}
              {edital.lance_sugerido_min != null && (
                <div style={{ background: "#F8F8F6", borderRadius: 8, padding: 14 }}>
                  <div style={{ fontSize: 12, color: "#8A8A85" }}>Faixa de lance</div>
                  <div style={{ fontSize: 15, fontWeight: 600, color: "#1A1A18" }}>{formatBRL(edital.lance_sugerido_min)} — {formatBRL(edital.lance_sugerido_max)}</div>
                </div>
              )}
            </div>

            {/* Processing banner */}
            <ProcessingBanner status={status} startedAt={processingStarted} />
            <ErrorBanner status={status} onRetry={() => handleAction(status === "erro_analise" ? "analisar" : "planilha")} />

            {/* Acoes */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#1A1A18", marginBottom: 10 }}>Acoes disponiveis</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {(status === "analisando" || status === "precificando") && (
                  <div style={{ fontSize: 12, color: "#8A8A85", fontStyle: "italic" }}>Processamento em andamento...</div>
                )}
                {(status === "novo" || status === "classificado" || status === "erro_analise") && (
                  <>
                    <ActionBtn primary onClick={() => handleAction("analisar")}>Analisar edital</ActionBtn>
                    {!pncpId?.startsWith("MANUAL") && <ActionBtn onClick={() => window.open(`/api/editais/${pncpId}/pdf/download`, '_blank')}>PDF</ActionBtn>}
                    <ActionBtn onClick={() => setShowPostosForm(!showPostosForm)}>Inserir MDO</ActionBtn>
                  </>
                )}
                {(status === "analisado" || status === "go" || status === "go_com_ressalvas" || status === "erro_precificacao") && (
                  <>
                    <ActionBtn primary onClick={() => handleAction("planilha")}>Gerar planilha competitiva</ActionBtn>
                    {!pncpId?.startsWith("MANUAL") && <ActionBtn onClick={() => window.open(`/api/editais/${pncpId}/pdf/download`, '_blank')}>PDF</ActionBtn>}
                    <ActionBtn onClick={() => setShowPostosForm(!showPostosForm)}>Editar MDO</ActionBtn>
                  </>
                )}
                {status === "precificado" && (
                  <>
                    <ActionBtn primary onClick={() => handleAction("competitivo")}>Ver dossie competitivo</ActionBtn>
                    <ActionBtn onClick={() => window.open(`/api/editais/${pncpId}/planilha/download`)}>Baixar planilha .xlsx</ActionBtn>
                    <ActionBtn onClick={() => handleAction("planilha")}>Regerar planilha</ActionBtn>
                  </>
                )}
                {status === "competitivo_pronto" && (
                  <>
                    <ActionBtn primary onClick={() => handleAction("competitivo")}>Dossie</ActionBtn>
                    <ActionBtn onClick={() => window.open(`/api/editais/${pncpId}/planilha/download`)}>Planilha</ActionBtn>
                  </>
                )}
                {edital.link_edital && <ActionBtn onClick={() => window.open(edital.link_edital)}>Ver no PNCP</ActionBtn>}
                {status !== "novo" && status !== "classificado" && (
                  <ActionBtn onClick={async () => { await api.resetar(pncpId); const fresh = await api.getEdital(pncpId); setEdital(fresh); onRefresh?.(); }}>Reanalisar</ActionBtn>
                )}
                <ActionBtn onClick={() => handleAction("arquivar")}>Arquivar</ActionBtn>
              </div>
            </div>

            {/* Upload de planilha manual */}
            <UploadPlanilha pncpId={pncpId} onUploaded={async () => { const fresh = await api.getEdital(pncpId); setEdital(fresh); onRefresh?.(); }} />

            {/* Documentos do edital */}
            {!pncpId?.startsWith("MANUAL") && <ArquivosSection pncpId={pncpId} />}

            {/* Form manual de postos */}
            {showPostosForm && (
              <PostosManualForm
                pncpId={pncpId}
                onSaved={() => {
                  setShowPostosForm(false);
                  api.getEdital(pncpId).then(setEdital);
                  onRefresh?.();
                }}
              />
            )}

            {/* Recomendacao Agente 4 */}
            {status === "competitivo_pronto" && edital.analise_competitiva_json && (
              <div style={{ background: "#F0FDF9", borderRadius: 10, padding: 16, border: "1px solid #CCFBF1", marginBottom: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#134E4A", marginBottom: 8 }}>Recomendacao do Agente 4</div>
                <div style={{ fontSize: 13, color: "#115E59", lineHeight: 1.6 }}>
                  Lance sugerido: <strong>{formatBRL(edital.analise_competitiva_json?.lance_sugerido)}</strong>.
                  {edital.analise_competitiva_json?.justificativa && ` ${edital.analise_competitiva_json.justificativa}`}
                </div>
              </div>
            )}

            {/* Resultado da precificacao */}
            {(status === "precificado" || status === "competitivo_pronto") && (
              <div style={{ background: "#111114", borderRadius: 10, padding: 16, border: "1px solid #2A2A32", marginBottom: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: "#BEFF3A", marginBottom: 12 }}>Resultado da Precificacao</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 12 }}>
                  <div>
                    <div style={{ fontSize: 10, color: "#5A5854", textTransform: "uppercase" }}>Proposta</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: "#EEEEE8" }}>{formatBRL(edital.valor_proposta)}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: "#5A5854", textTransform: "uppercase" }}>Margem</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: "#2EDDA8" }}>{edital.margem_percentual ? `${edital.margem_percentual.toFixed(1)}%` : "—"}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: "#5A5854", textTransform: "uppercase" }}>Teto edital</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: "#98968E" }}>{formatBRL(edital.valor_estimado)}</div>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={() => window.open(`/api/editais/${pncpId}/planilha/download`)}
                    style={{ flex: 1, padding: "10px", background: "#BEFF3A", color: "#09090B", border: "none", borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: "pointer" }}>
                    Baixar Planilha XLSX
                  </button>
                </div>
              </div>
            )}

            {/* Analise - postos identificados (colapsavel) */}
            {edital.analise_json?.postos_trabalho?.length > 0 && (
              <details style={{ marginBottom: 16 }}>
                <summary style={{ fontSize: 13, fontWeight: 600, color: "#98968E", cursor: "pointer", padding: "8px 0" }}>
                  Postos identificados ({edital.analise_json.postos_trabalho.length}) — {edital.analise_json._postos_fonte === "tabela_pdf" ? "extraido do PDF" : edital.analise_json._postos_fonte === "manual" ? "manual" : "IA"}
                </summary>
                <div style={{ background: "#111114", borderRadius: 10, padding: 14, border: "1px solid #2A2A32", marginTop: 6 }}>
                  {edital.analise_json.postos_trabalho.map((p, i) => (
                    <div key={i} style={{ fontSize: 12, color: "#98968E", padding: "3px 0" }}>
                      {p.funcao_display || p.funcao} — {p.quantidade}x — {p.jornada || "44h"}
                    </div>
                  ))}
                </div>
              </details>
            )}

            {/* Ranking de empresas */}
            {edital.analise_json?.empresas_ranking?.length > 0 && (
              <div style={{ background: "#F8F8F6", borderRadius: 10, padding: 14, border: "1px solid #E8E8E4", marginBottom: 16 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#1A1A18", marginBottom: 10 }}>Empresa recomendada</div>
                {edital.analise_json.empresas_ranking.map((emp, i) => {
                  const isBest = i === 0 && emp.viavel;
                  const bg = !emp.viavel ? "#FEF2F2" : isBest ? "#F0FDF4" : "#FFFFFF";
                  const border = !emp.viavel ? "#FEE2E2" : isBest ? "#BBF7D0" : "#E8E8E4";
                  return (
                    <div key={i} style={{ background: bg, border: `1px solid ${border}`, borderRadius: 8, padding: 10, marginBottom: 6 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          {isBest && <span style={{ background: "#16A34A", color: "#FFF", fontSize: 10, padding: "1px 6px", borderRadius: 4, fontWeight: 700 }}>RECOMENDADA</span>}
                          {!emp.viavel && <span style={{ background: "#DC2626", color: "#FFF", fontSize: 10, padding: "1px 6px", borderRadius: 4, fontWeight: 700 }}>INVIAVEL</span>}
                          <span style={{ fontSize: 13, fontWeight: 600, color: "#1A1A18" }}>{emp.nome}</span>
                        </div>
                        <span style={{ fontSize: 12, fontWeight: 600, color: isBest ? "#16A34A" : "#8A8A85" }}>{emp.score} pts</span>
                      </div>
                      <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 2 }}>
                        {emp.regime?.replace("_", " ")} {emp.desonerada ? "| Desonerada" : ""}
                      </div>
                      {emp.vantagens?.length > 0 && (
                        <div style={{ fontSize: 11, color: "#065F46" }}>
                          {emp.vantagens.join(" | ")}
                        </div>
                      )}
                      {emp.motivo && (
                        <div style={{ fontSize: 11, color: emp.viavel ? "#92400E" : "#991B1B", marginTop: 2 }}>
                          {emp.motivo}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* No-Go reason */}
            {status === "nogo" && edital.motivo_nogo && (
              <div style={{ background: "#FEF2F2", borderRadius: 10, padding: 16, border: "1px solid #FEE2E2", marginBottom: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#991B1B", marginBottom: 8 }}>Motivo do No-Go</div>
                <div style={{ fontSize: 13, color: "#7F1D1D", lineHeight: 1.6 }}>{edital.motivo_nogo}</div>
              </div>
            )}

            {/* Info adicional */}
            <div style={{ fontSize: 12, color: "#AEAEA8", marginTop: 20 }}>
              <div>PNCP ID: {edital.pncp_id}</div>
              <div>UF: {edital.uf} | Municipio: {edital.municipio || "N/I"}</div>
              <div>Encerramento: {edital.data_encerramento || "N/I"}</div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
