import { useState, useEffect } from "react";

const inputStyle = {
  width: "100%", padding: "8px 12px", border: "1px solid #D1D5DB",
  borderRadius: 6, fontSize: 13, boxSizing: "border-box", fontFamily: "monospace",
};
const labelStyle = { fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 };
const cardStyle = { background: "#FFF", borderRadius: 10, padding: 18, border: "1px solid #E5E7EB", marginBottom: 16 };
const btnPrimary = { padding: "7px 16px", background: "#1A1A18", color: "#FFF", border: "none", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer" };
const btnSecondary = { padding: "7px 16px", background: "#F3F4F6", color: "#1A1A18", border: "1px solid #E5E7EB", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer" };

export default function IntegracoesEmpresa({ empresaId, empresaNome }) {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ trello_api_key: "", trello_token: "", trello_board_id: "", drive_folder_id: "" });
  const [salvando, setSalvando] = useState(false);
  const [testando, setTestando] = useState(null);
  const [msg, setMsg] = useState("");
  const [erro, setErro] = useState("");

  const token = localStorage.getItem("token");
  const h = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const carregar = async () => {
    const r = await fetch(`/api/perfil/empresas/${empresaId}/integracoes`, { headers: h });
    if (r.ok) {
      const d = await r.json();
      setData(d);
      setForm({
        trello_api_key: "",
        trello_token: "",
        trello_board_id: d.trello_board_id || "",
        drive_folder_id: d.drive_folder_id || "",
      });
    }
  };

  useEffect(() => { carregar(); }, [empresaId]);

  const salvar = async () => {
    setSalvando(true);
    setMsg(""); setErro("");
    const body = {};
    if (form.trello_api_key) body.trello_api_key = form.trello_api_key;
    if (form.trello_token) body.trello_token = form.trello_token;
    if (form.trello_board_id !== (data?.trello_board_id || "")) body.trello_board_id = form.trello_board_id;
    if (form.drive_folder_id !== (data?.drive_folder_id || "")) body.drive_folder_id = form.drive_folder_id;
    const r = await fetch(`/api/perfil/empresas/${empresaId}/integracoes`, {
      method: "PUT", headers: h, body: JSON.stringify(body),
    });
    if (r.ok) {
      setMsg("Salvo.");
      await carregar();
    } else {
      setErro("Erro ao salvar");
    }
    setSalvando(false);
  };

  const testar = async (qual) => {
    setTestando(qual);
    setMsg(""); setErro("");
    const r = await fetch(`/api/perfil/empresas/${empresaId}/integracoes/testar-${qual}`, {
      method: "POST", headers: h,
    });
    const d = await r.json();
    if (r.ok) {
      if (qual === "trello") {
        setMsg(`✓ Board "${d.board_nome}" — ${d.listas.length} listas: ${d.listas.map(l => l.name).join(", ")}`);
      } else {
        setMsg(`✓ Pasta "${d.pasta_nome}" acessível no Drive`);
      }
    } else {
      setErro(d.detail || "Falha no teste");
    }
    setTestando(null);
  };

  if (!data) return <div style={{ color: "#AEAEA8" }}>Carregando…</div>;

  return (
    <div>
      <h3 style={{ fontSize: 16, fontWeight: 600, color: "#1A1A18", margin: "0 0 4px" }}>
        Integrações — {empresaNome}
      </h3>
      <p style={{ fontSize: 12, color: "#6B7280", margin: "0 0 16px" }}>
        Conecte Trello e Google Drive desta empresa. Cada empresa do seu cadastro tem credenciais próprias.
      </p>

      {msg && <div style={{ background: "#ECFDF5", border: "1px solid #A7F3D0", color: "#065F46", padding: "8px 12px", borderRadius: 6, fontSize: 12, marginBottom: 12 }}>{msg}</div>}
      {erro && <div style={{ background: "#FEF2F2", border: "1px solid #FCA5A5", color: "#991B1B", padding: "8px 12px", borderRadius: 6, fontSize: 12, marginBottom: 12 }}>{erro}</div>}

      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h4 style={{ fontSize: 14, fontWeight: 700, margin: 0 }}>Trello</h4>
          <button onClick={() => testar("trello")} disabled={testando === "trello"} style={btnSecondary}>
            {testando === "trello" ? "Testando…" : "Testar conexão"}
          </button>
        </div>

        <div style={{ marginBottom: 10 }}>
          <label style={labelStyle}>API Key {data.trello_api_key_set && <span style={{ color: "#16A34A" }}>· salva ({data.trello_api_key})</span>}</label>
          <input style={inputStyle} type="password" value={form.trello_api_key}
            onChange={e => setForm({ ...form, trello_api_key: e.target.value })}
            placeholder={data.trello_api_key_set ? "deixe em branco pra manter" : "32 caracteres do painel Trello"} />
        </div>

        <div style={{ marginBottom: 10 }}>
          <label style={labelStyle}>Token {data.trello_token_set && <span style={{ color: "#16A34A" }}>· salvo ({data.trello_token})</span>}</label>
          <input style={inputStyle} type="password" value={form.trello_token}
            onChange={e => setForm({ ...form, trello_token: e.target.value })}
            placeholder={data.trello_token_set ? "deixe em branco pra manter" : "começa com ATTA"} />
        </div>

        <div style={{ marginBottom: 10 }}>
          <label style={labelStyle}>Board ID</label>
          <input style={inputStyle} value={form.trello_board_id}
            onChange={e => setForm({ ...form, trello_board_id: e.target.value })}
            placeholder="ID do board (24 chars hex)" />
        </div>

        <div style={{ fontSize: 11, color: "#6B7280", marginTop: 8 }}>
          Não tem? <a href="https://trello.com/power-ups/admin" target="_blank" rel="noreferrer" style={{ color: "#2563EB" }}>Crie um Power-Up</a> e gere API Key + Token.
        </div>
      </div>

      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h4 style={{ fontSize: 14, fontWeight: 700, margin: 0 }}>Google Drive</h4>
          <button onClick={() => testar("drive")} disabled={testando === "drive" || !form.drive_folder_id} style={btnSecondary}>
            {testando === "drive" ? "Testando…" : "Testar acesso"}
          </button>
        </div>

        <div style={{ marginBottom: 10 }}>
          <label style={labelStyle}>ID da pasta raiz</label>
          <input style={inputStyle} value={form.drive_folder_id}
            onChange={e => setForm({ ...form, drive_folder_id: e.target.value })}
            placeholder="ID da pasta no Drive (visível na URL)" />
        </div>

        <div style={{ fontSize: 11, color: "#6B7280" }}>
          {data.drive_sa_disponivel
            ? "Service Account configurado no servidor. Compartilhe a pasta com o email do SA (editor) e cole o ID aqui."
            : <span style={{ color: "#92400E" }}>⚠ Servidor ainda não tem Service Account Drive configurado.</span>
          }
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
        <button onClick={salvar} disabled={salvando} style={btnPrimary}>
          {salvando ? "Salvando…" : "Salvar"}
        </button>
      </div>
    </div>
  );
}
