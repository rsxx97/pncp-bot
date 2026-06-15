import { useState, useEffect } from "react";
import { api } from "../api";

const fmtData = (s) => {
  if (!s) return "—";
  try { return new Date(s).toLocaleDateString("pt-BR"); } catch { return s; }
};

const cardStyle = { background: "#FFF", borderRadius: 10, padding: 16, border: "1px solid #E5E7EB" };
const btnPrimary = { padding: "6px 14px", background: "#16A34A", color: "#FFF", border: "none", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer" };
const btnDanger = { padding: "6px 14px", background: "#FEF2F2", color: "#DC2626", border: "1px solid #FCA5A5", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer" };

export default function AdminPanel() {
  const [pendentes, setPendentes] = useState([]);
  const [todos, setTodos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");

  const recarregar = async () => {
    setLoading(true);
    setErro("");
    try {
      const [p, t] = await Promise.all([api.listarPendentes(), api.listarTenants()]);
      setPendentes(p);
      setTodos(t);
    } catch (e) {
      setErro(e.message);
    }
    setLoading(false);
  };

  useEffect(() => { recarregar(); }, []);

  const aprovar = async (id) => {
    await api.aprovarTenant(id);
    await recarregar();
  };

  const rejeitar = async (id) => {
    if (!confirm("Rejeitar este tenant? A conta será desativada.")) return;
    await api.rejeitarTenant(id);
    await recarregar();
  };

  if (loading) return <div style={{ color: "#AEAEA8", padding: 20 }}>Carregando…</div>;
  if (erro) return <div style={{ color: "#DC2626", padding: 20 }}>Erro: {erro}</div>;

  const ativos = todos.filter(t => t.aprovado && t.ativo);
  const inativos = todos.filter(t => !t.ativo);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, color: "#1A1A18" }}>
      <section>
        <h2 style={{ fontSize: 18, fontWeight: 600, margin: "0 0 4px", color: "#EEEEE8" }}>
          Pendentes de aprovação ({pendentes.length})
        </h2>
        <p style={{ fontSize: 12, color: "#98968E", margin: "0 0 12px" }}>
          Tenants que se cadastraram via /cadastro e aguardam liberação.
        </p>
        {pendentes.length === 0 ? (
          <div style={{ ...cardStyle, color: "#6B7280", fontSize: 13 }}>Nenhum cadastro pendente.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {pendentes.map(t => (
              <div key={t.id} style={cardStyle}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>{t.nome_empresa}</div>
                    <div style={{ fontSize: 12, color: "#6B7280" }}>{t.email} · CNPJ {t.cnpj || "—"}</div>
                    <div style={{ fontSize: 11, color: "#9CA3AF", marginTop: 4 }}>Cadastro: {fmtData(t.created_at)}</div>
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button style={btnPrimary} onClick={() => aprovar(t.id)}>Aprovar</button>
                    <button style={btnDanger} onClick={() => rejeitar(t.id)}>Rejeitar</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 style={{ fontSize: 18, fontWeight: 600, margin: "0 0 12px", color: "#EEEEE8" }}>
          Tenants ativos ({ativos.length})
        </h2>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {ativos.map(t => (
            <div key={t.id} style={{ ...cardStyle, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>
                  {t.nome_empresa}
                  {t.role === "super_admin" && (
                    <span style={{ fontSize: 10, background: "#1A1A18", color: "#FFF", padding: "2px 6px", borderRadius: 4, marginLeft: 8 }}>ADMIN</span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: "#6B7280" }}>{t.email} · plano {t.plano}</div>
              </div>
              {t.role !== "super_admin" && (
                <button style={btnDanger} onClick={() => rejeitar(t.id)}>Desativar</button>
              )}
            </div>
          ))}
        </div>
      </section>

      {inativos.length > 0 && (
        <section>
          <h2 style={{ fontSize: 16, fontWeight: 600, margin: "0 0 12px", color: "#98968E" }}>
            Desativados ({inativos.length})
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {inativos.map(t => (
              <div key={t.id} style={{ ...cardStyle, opacity: 0.6 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: "#6B7280" }}>{t.nome_empresa}</div>
                <div style={{ fontSize: 11, color: "#9CA3AF" }}>{t.email}</div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
