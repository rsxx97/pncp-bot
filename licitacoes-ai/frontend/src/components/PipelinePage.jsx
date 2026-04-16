import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import EditalTable from "./EditalTable";
import EditalDetailPanel from "./EditalDetail";

const C = {
  bg: "#09090B", s1: "#111114", s2: "#18181C", s3: "#222228",
  b1: "#2A2A32", b2: "#3A3A44",
  t1: "#EEEEE8", t2: "#98968E", t3: "#5A5854",
  ac: "#BEFF3A", rd: "#FF4D4D", am: "#FFB038", tl: "#2EDDA8", bl: "#5A9EF7", pr: "#A78BFA",
};
const mono = "'JetBrains Mono', monospace";

const fmt = v => !v ? "—" : new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v);
const pct = v => v == null ? "—" : (v > 1 ? v.toFixed(1) + "%" : (v * 100).toFixed(1) + "%");

function Card({ children, style = {} }) {
  return <div style={{ background: C.s2, border: `1px solid ${C.b1}`, borderRadius: 10, padding: 16, ...style }}>{children}</div>;
}

function Stat({ label, value, color = C.t1, sub = null }) {
  return (
    <div>
      <div style={{ fontFamily: mono, fontSize: 22, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 9, color: C.t3, marginTop: 2, textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</div>
      {sub && <div style={{ fontSize: 10, color: C.t2, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function Badge({ color, children }) {
  return <span style={{ fontSize: 9, fontWeight: 700, padding: "3px 8px", borderRadius: 4, background: color + "22", color, textTransform: "uppercase", letterSpacing: 0.5 }}>{children}</span>;
}

export default function PipelinePage() {
  const [editais, setEditais] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedPncpId, setSelectedPncpId] = useState(null);
  const [filter, setFilter] = useState("todos");
  const [searchText, setSearchText] = useState("");
  const [tipoFilter, setTipoFilter] = useState("todos");
  const [planilhaFilter, setPlanilhaFilter] = useState("todos");
  const [sortBy, setSortBy] = useState("valor");
  const [verificacao, setVerificacao] = useState(null);
  const [skills, setSkills] = useState(null);
  const [verificando, setVerificando] = useState(false);

  const loadEditais = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getEditais({ per_page: 500, sort: "-valor_estimado" });
      setEditais((data.items || []).filter(e => e.fonte !== "extension" && e.status !== "pregao_ext" && e.status !== "arquivado"));
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  const loadVerificacao = useCallback(async () => {
    try {
      const r = await fetch("/api/planilhas/verificacao/ultima");
      const d = await r.json();
      if (!d.erro) setVerificacao(d);
    } catch (e) {}
  }, []);

  const loadSkills = useCallback(async () => {
    try {
      const r = await fetch("/api/planilhas/skills/atual");
      const d = await r.json();
      if (!d.erro) setSkills(d);
    } catch (e) {}
  }, []);

  useEffect(() => {
    loadEditais();
    loadVerificacao();
    loadSkills();
  }, [loadEditais, loadVerificacao, loadSkills]);

  const executarVerificacao = async () => {
    setVerificando(true);
    try {
      await fetch("/api/planilhas/verificacao/executar", { method: "POST" });
      // Espera 5s e recarrega
      setTimeout(async () => {
        await loadVerificacao();
        setVerificando(false);
      }, 5000);
    } catch (e) { setVerificando(false); }
  };

  // Detecta tipo do edital
  const detectarTipo = (objeto) => {
    const obj = (objeto || "").toLowerCase();
    if (/obra|reforma|constru[cç][aã]o|paviment|drenagem|engenharia|amplia|restaur/i.test(obj)) return "obra";
    return "terceirizacao";
  };

  // Stats
  const stats = useMemo(() => {
    const total = editais.length;
    const comPlanilha = editais.filter(e => e.planilha_path).length;
    const obra = editais.filter(e => detectarTipo(e.objeto) === "obra").length;
    const terceirizacao = total - obra;
    const volume = editais.reduce((s, e) => s + (e.valor_estimado || 0), 0);
    return { total, comPlanilha, semPlanilha: total - comPlanilha, obra, terceirizacao, volume };
  }, [editais]);

  // Filtros
  const filtrados = useMemo(() => {
    let list = editais;

    // Filtro status
    if (filter === "com_plan") list = list.filter(e => e.planilha_path);
    else if (filter === "sem_plan") list = list.filter(e => !e.planilha_path);
    else if (filter === "novo") list = list.filter(e => ["novo", "classificado"].includes(e.status));
    else if (filter === "pronto") list = list.filter(e => ["precificado", "competitivo_pronto"].includes(e.status));

    // Tipo
    if (tipoFilter !== "todos") list = list.filter(e => detectarTipo(e.objeto) === tipoFilter);

    // Planilha
    if (planilhaFilter === "com") list = list.filter(e => e.planilha_path);
    else if (planilhaFilter === "sem") list = list.filter(e => !e.planilha_path);

    // Busca
    if (searchText.trim()) {
      const s = searchText.toLowerCase();
      list = list.filter(e =>
        (e.orgao_nome || "").toLowerCase().includes(s) ||
        (e.objeto || "").toLowerCase().includes(s) ||
        (e.uf || "").toLowerCase().includes(s) ||
        (e.pncp_id || "").toLowerCase().includes(s)
      );
    }

    // Ordenação
    list = [...list].sort((a, b) => {
      if (sortBy === "valor") return (b.valor_estimado || 0) - (a.valor_estimado || 0);
      if (sortBy === "score") return (b.score_relevancia || 0) - (a.score_relevancia || 0);
      if (sortBy === "prazo") return (a.data_encerramento || "z").localeCompare(b.data_encerramento || "z");
      return 0;
    });

    return list;
  }, [editais, filter, tipoFilter, planilhaFilter, searchText, sortBy]);

  const filters = [
    { key: "todos", label: "Todos", count: stats.total },
    { key: "com_plan", label: "Com Planilha", count: stats.comPlanilha },
    { key: "sem_plan", label: "Sem Planilha", count: stats.semPlanilha },
    { key: "novo", label: "Novos", count: editais.filter(e => ["novo", "classificado"].includes(e.status)).length },
    { key: "pronto", label: "Prontos", count: editais.filter(e => ["precificado", "competitivo_pronto"].includes(e.status)).length },
  ];

  return (
    <div>
      {/* KPIs principais */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 10, marginBottom: 16 }}>
        <Card><Stat label="Total Editais" value={stats.total} color={C.ac} /></Card>
        <Card><Stat label="Terceirização" value={stats.terceirizacao} color={C.tl} /></Card>
        <Card><Stat label="Obra/Reforma" value={stats.obra} color={C.bl} /></Card>
        <Card><Stat label="Com Planilha" value={stats.comPlanilha} color={C.ac} sub={`${((stats.comPlanilha/stats.total)*100||0).toFixed(0)}%`} /></Card>
        <Card><Stat label="Volume Total" value={fmt(stats.volume)} color={C.am} /></Card>
      </div>

      {/* Painel de verificação e skills */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
        {/* Verificação */}
        <Card>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: C.t1, textTransform: "uppercase", letterSpacing: 1 }}>
              Verificação Cruzada de Planilhas
            </div>
            <button onClick={executarVerificacao} disabled={verificando}
              style={{
                fontFamily: mono, fontSize: 10, padding: "5px 12px", borderRadius: 6,
                border: "none", background: verificando ? C.s3 : C.ac, color: C.bg,
                cursor: verificando ? "wait" : "pointer", fontWeight: 700,
              }}>
              {verificando ? "Verificando..." : "Executar Bot"}
            </button>
          </div>
          {verificacao ? (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginBottom: 10 }}>
                <div>
                  <div style={{ fontFamily: mono, fontSize: 18, fontWeight: 700, color: C.tl }}>{verificacao.ok || 0}</div>
                  <div style={{ fontSize: 9, color: C.t3, textTransform: "uppercase" }}>OK</div>
                </div>
                <div>
                  <div style={{ fontFamily: mono, fontSize: 18, fontWeight: 700, color: C.am }}>{verificacao.avisos || 0}</div>
                  <div style={{ fontSize: 9, color: C.t3, textTransform: "uppercase" }}>Avisos</div>
                </div>
                <div>
                  <div style={{ fontFamily: mono, fontSize: 18, fontWeight: 700, color: C.rd }}>{verificacao.criticos || 0}</div>
                  <div style={{ fontSize: 9, color: C.t3, textTransform: "uppercase" }}>Críticos</div>
                </div>
              </div>
              {verificacao.benchmark_global?.bdis && (
                <div style={{ fontSize: 10, color: C.t2 }}>
                  BDI médio: <span style={{ color: C.t1, fontFamily: mono }}>{verificacao.benchmark_global.bdis.media?.toFixed(2)}%</span>
                  {" · "}
                  Custo/func: <span style={{ color: C.t1, fontFamily: mono }}>
                    {verificacao.benchmark_global.custos_medios_func ? "R$ " + verificacao.benchmark_global.custos_medios_func.media?.toFixed(0) : "—"}
                  </span>
                </div>
              )}
              <div style={{ fontSize: 9, color: C.t3, marginTop: 6 }}>
                Última verificação: {verificacao.data ? new Date(verificacao.data).toLocaleString("pt-BR") : "—"}
              </div>
            </>
          ) : (
            <div style={{ fontSize: 11, color: C.t3, textAlign: "center", padding: 20 }}>
              Nenhuma verificação disponível. Clique em "Executar Bot".
            </div>
          )}
        </Card>

        {/* Skills */}
        <Card>
          <div style={{ fontSize: 11, fontWeight: 700, color: C.t1, textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>
            Skills PNCP (Planilhas Reais Absorvidas)
          </div>
          {skills ? (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10, marginBottom: 10 }}>
                <div>
                  <div style={{ fontFamily: mono, fontSize: 16, fontWeight: 700, color: C.pr }}>
                    {skills.total_planilhas_analisadas || 0}
                  </div>
                  <div style={{ fontSize: 9, color: C.t3, textTransform: "uppercase" }}>Planilhas Analisadas</div>
                </div>
                <div>
                  <div style={{ fontFamily: mono, fontSize: 16, fontWeight: 700, color: C.pr }}>
                    {Object.keys(skills.salarios_por_cargo || {}).length}
                  </div>
                  <div style={{ fontSize: 9, color: C.t3, textTransform: "uppercase" }}>Cargos Mapeados</div>
                </div>
              </div>
              <div style={{ fontSize: 10, color: C.t2 }}>
                Encargos médio: <span style={{ color: C.t1, fontFamily: mono }}>{skills.encargos_media?.toFixed(2) || "—"}%</span>
                {" · "}
                BDI médio: <span style={{ color: C.t1, fontFamily: mono }}>{skills.bdi_media?.toFixed(2) || "—"}%</span>
              </div>
              {skills.beneficios_media?.vale_transporte && (
                <div style={{ fontSize: 10, color: C.t2, marginTop: 4 }}>
                  VT médio: <span style={{ color: C.t1, fontFamily: mono }}>R$ {skills.beneficios_media.vale_transporte.toFixed(2)}/mês</span>
                </div>
              )}
            </>
          ) : (
            <div style={{ fontSize: 11, color: C.t3, textAlign: "center", padding: 20 }}>
              Skills ainda não disponíveis.
            </div>
          )}
        </Card>
      </div>

      {/* Filtros */}
      <Card style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {/* Linha 1: filtros principais */}
          <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
            {filters.map(f => (
              <button key={f.key} onClick={() => setFilter(f.key)}
                style={{
                  fontFamily: mono, fontSize: 10, padding: "5px 12px", borderRadius: 6, cursor: "pointer", fontWeight: 600,
                  border: `1px solid ${filter === f.key ? C.b2 : C.b1}`,
                  background: filter === f.key ? C.s3 : "transparent",
                  color: filter === f.key ? C.t1 : C.t3,
                }}>
                {f.label} ({f.count})
              </button>
            ))}
          </div>

          {/* Linha 2: tipo + ordenação */}
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", gap: 5 }}>
              <span style={{ fontSize: 9, color: C.t3, alignSelf: "center", textTransform: "uppercase" }}>Tipo:</span>
              {[
                { key: "todos", label: "Todos" },
                { key: "terceirizacao", label: "Terceirização" },
                { key: "obra", label: "Obra" },
                { key: "aquisicao", label: "Aquisição" },
              ].map(t => (
                <button key={t.key} onClick={() => setTipoFilter(t.key)}
                  style={{
                    fontFamily: mono, fontSize: 10, padding: "4px 10px", borderRadius: 5, cursor: "pointer",
                    border: "none", background: tipoFilter === t.key ? C.s3 : "transparent",
                    color: tipoFilter === t.key ? C.ac : C.t3, fontWeight: 600,
                  }}>
                  {t.label}
                </button>
              ))}
            </div>
            <div style={{ display: "flex", gap: 4 }}>
              <span style={{ fontSize: 9, color: C.t3, alignSelf: "center", textTransform: "uppercase" }}>Ordenar:</span>
              {[
                { key: "valor", label: "Valor" },
                { key: "score", label: "Score" },
                { key: "prazo", label: "Prazo" },
              ].map(s => (
                <button key={s.key} onClick={() => setSortBy(s.key)}
                  style={{
                    fontFamily: mono, fontSize: 9, padding: "3px 8px", borderRadius: 4, cursor: "pointer",
                    border: "none", background: sortBy === s.key ? C.s3 : "transparent",
                    color: sortBy === s.key ? C.ac : C.t3, fontWeight: 600,
                  }}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Busca */}
          <input
            placeholder="Buscar por órgão, objeto, UF, PNCP ID..."
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            style={{
              width: "100%", padding: "8px 14px", boxSizing: "border-box", outline: "none",
              background: C.s1, border: `1px solid ${C.b1}`, borderRadius: 8,
              fontSize: 12, color: C.t1, fontFamily: mono,
            }}
          />
        </div>
      </Card>

      {/* Resultados */}
      <div style={{ fontSize: 10, color: C.t3, marginBottom: 8, fontFamily: mono }}>
        {filtrados.length} editais · Volume: {fmt(filtrados.reduce((s, e) => s + (e.valor_estimado || 0), 0))}
      </div>

      {loading ? (
        <div style={{ padding: 40, textAlign: "center", color: C.t3, fontFamily: mono, fontSize: 12 }}>
          Carregando editais...
        </div>
      ) : (
        <EditalTable editais={filtrados} onSelect={setSelectedPncpId} onRefresh={loadEditais} dark />
      )}

      {selectedPncpId && (
        <EditalDetailPanel pncpId={selectedPncpId} onClose={() => setSelectedPncpId(null)} onRefresh={loadEditais} />
      )}
    </div>
  );
}
