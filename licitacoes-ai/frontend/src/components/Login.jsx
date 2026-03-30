import { useState } from "react";

export default function Login({ onLogin }) {
  const [mode, setMode] = useState("login"); // login | register
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [nome, setNome] = useState("");
  const [cnpj, setCnpj] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const url = mode === "login" ? "/api/auth/login" : "/api/auth/register";
    const body = mode === "login"
      ? { email, senha }
      : { email, senha, nome_empresa: nome, cnpj: cnpj || null };

    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await resp.json();
      if (!resp.ok) {
        const msg = typeof data.detail === "string" ? data.detail : Array.isArray(data.detail) ? data.detail.map(d => d.msg).join(", ") : "Erro desconhecido";
        throw new Error(msg);
      }
      localStorage.setItem("token", data.token);
      localStorage.setItem("tenant", JSON.stringify(data.tenant));
      onLogin(data.tenant, data.token);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const inputStyle = {
    width: "100%", padding: "10px 14px", border: "1px solid #D1D5DB",
    borderRadius: 8, fontSize: 14, outline: "none", boxSizing: "border-box",
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#F9FAFB", fontFamily: "'DM Sans', sans-serif" }}>
      <div style={{ width: 380, background: "#FFF", borderRadius: 16, padding: 32, boxShadow: "0 4px 24px rgba(0,0,0,0.08)" }}>
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: "0 0 4px" }}>Licitacoes AI</h1>
          <p style={{ fontSize: 13, color: "#6B7280", margin: 0 }}>
            {mode === "login" ? "Acesse sua conta" : "Crie sua conta gratuita"}
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          {mode === "register" && (
            <>
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>Nome da empresa</label>
                <input style={inputStyle} value={nome} onChange={e => setNome(e.target.value)} placeholder="Ex: Minha Empresa Ltda" required />
              </div>
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>CNPJ (opcional)</label>
                <input style={inputStyle} value={cnpj} onChange={e => setCnpj(e.target.value)} placeholder="00.000.000/0001-00" />
              </div>
            </>
          )}

          <div style={{ marginBottom: 12 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>Email</label>
            <input style={inputStyle} type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="seu@email.com" required />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>Senha</label>
            <input style={inputStyle} type="password" value={senha} onChange={e => setSenha(e.target.value)} placeholder="Sua senha" required minLength={6} />
          </div>

          {error && <div style={{ color: "#DC2626", fontSize: 13, marginBottom: 12, textAlign: "center" }}>{error}</div>}

          <button type="submit" disabled={loading}
            style={{ width: "100%", padding: "10px 0", background: "#1A1A18", color: "#FFF", border: "none", borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: "pointer" }}>
            {loading ? "Aguarde..." : mode === "login" ? "Entrar" : "Criar conta"}
          </button>
        </form>

        <div style={{ textAlign: "center", marginTop: 16 }}>
          <button onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
            style={{ background: "none", border: "none", color: "#2563EB", fontSize: 13, cursor: "pointer" }}>
            {mode === "login" ? "Nao tem conta? Cadastre-se" : "Ja tem conta? Faca login"}
          </button>
        </div>
      </div>
    </div>
  );
}
