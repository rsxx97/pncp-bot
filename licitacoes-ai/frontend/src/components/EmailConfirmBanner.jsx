import { useState } from "react";

export default function EmailConfirmBanner({ tenant }) {
  const [estado, setEstado] = useState("idle"); // idle | enviando | enviado | erro

  if (!tenant || tenant.email_verificado) return null;

  const reenviar = async () => {
    setEstado("enviando");
    try {
      const r = await fetch("/api/auth/reenviar", {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      setEstado(r.ok ? "enviado" : "erro");
    } catch {
      setEstado("erro");
    }
  };

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
      background: "linear-gradient(135deg, #FFF7ED, #FFFBEB)", border: "1px solid #FCD9A8",
      borderRadius: 12, padding: "12px 16px", marginBottom: 16,
    }}>
      <span style={{ fontSize: 18 }}>📧</span>
      <div style={{ flex: 1, minWidth: 220 }}>
        <div style={{ fontSize: 13.5, fontWeight: 700, color: "#92400E" }}>Confirme seu e-mail</div>
        <div style={{ fontSize: 12.5, color: "#B45309" }}>
          Enviamos um link de confirmação para <b>{tenant.email}</b>. Verifique a caixa de entrada (e o spam).
        </div>
      </div>
      {estado === "enviado" ? (
        <span style={{ fontSize: 12.5, fontWeight: 700, color: "#16A34A" }}>✓ E-mail reenviado</span>
      ) : (
        <button onClick={reenviar} disabled={estado === "enviando"}
          style={{ padding: "7px 16px", background: "#92400E", color: "#FFF", border: "none", borderRadius: 8, fontSize: 12.5, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap" }}>
          {estado === "enviando" ? "Enviando…" : estado === "erro" ? "Tentar de novo" : "Reenviar e-mail"}
        </button>
      )}
    </div>
  );
}
