import { useEffect, useState } from "react";
import { radarApi } from "./api";

export default function AlertasPage() {
  const [data, setData] = useState(null);
  const [msg, setMsg] = useState("");
  const [erro, setErro] = useState("");
  const [testando, setTestando] = useState(null);

  const carregar = async () => setData(await radarApi.listarAlertas());
  useEffect(() => { carregar(); }, []);

  const toggle = async (tipo, canal, ativo) => {
    const regras = data.matriz[tipo][canal].regras || {};
    await radarApi.salvarAlerta({ tipo_evento: tipo, canal, ativo, regras });
    setData(prev => ({
      ...prev,
      matriz: { ...prev.matriz, [tipo]: { ...prev.matriz[tipo], [canal]: { ...prev.matriz[tipo][canal], ativo } } },
    }));
  };

  const testar = async (canal, destino) => {
    setTestando(canal); setMsg(""); setErro("");
    try {
      const r = await radarApi.testarCanal({ canal, destino });
      if (r.status === "enviado") setMsg(`${canal}: ✓ enviado`);
      else setErro(`${canal}: ${r.erro || r.status}`);
    } catch (e) { setErro(`${canal}: ${e.message}`); }
    setTestando(null);
  };

  if (!data) return <div style={{ color: "#98968E", padding: 20 }}>Carregando…</div>;

  return (
    <div style={{ color: "#EEEEE8" }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginTop: 0 }}>Alertas — Matriz de eventos × canais</h2>
      <p style={{ fontSize: 12, color: "#98968E", marginTop: 0 }}>
        Marque por evento e canal o que deve ser disparado. Use os botões "Testar" pra validar antes.
      </p>

      {msg && <div style={{ background: "#16A34A22", border: "1px solid #16A34A66", color: "#34D399", padding: "8px 12px", borderRadius: 6, fontSize: 12, marginBottom: 10 }}>{msg}</div>}
      {erro && <div style={{ background: "#DC262622", border: "1px solid #DC262666", color: "#F87171", padding: "8px 12px", borderRadius: 6, fontSize: 12, marginBottom: 10 }}>{erro}</div>}

      <div style={{ background: "#18181C", padding: 12, borderRadius: 8, marginBottom: 16, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 8 }}>
        {data.canais.map(c => (
          <div key={c} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ flex: 1, fontSize: 11, fontFamily: "monospace", fontWeight: 600, textTransform: "uppercase" }}>{c}</span>
            <button onClick={() => testar(c, prompt(`Destino para ${c} (JSON):`, defaultDestino(c)).startsWith("{") ? JSON.parse(prompt(`Destino para ${c} (JSON):`, defaultDestino(c))) : {})}
              disabled={testando === c}
              style={{ fontSize: 10, padding: "3px 8px", background: "#222228", color: "#EEEEE8", border: "1px solid #2A2A32", borderRadius: 4, cursor: "pointer" }}>
              {testando === c ? "…" : "Testar"}
            </button>
          </div>
        ))}
      </div>

      <div style={{ overflowX: "auto", background: "#0F0F12", borderRadius: 8, border: "1px solid #2A2A32" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
          <thead>
            <tr style={{ background: "#18181C", borderBottom: "1px solid #2A2A32" }}>
              <th style={{ padding: "10px 12px", textAlign: "left", color: "#98968E", fontWeight: 600 }}>Evento</th>
              {data.canais.map(c => (
                <th key={c} style={{ padding: "10px 6px", textAlign: "center", color: "#98968E", fontFamily: "monospace", textTransform: "uppercase", fontSize: 10 }}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.tipos.map(t => (
              <tr key={t} style={{ borderBottom: "1px solid #18181C" }}>
                <td style={{ padding: "8px 12px", fontFamily: "monospace", color: "#EEEEE8" }}>{t}</td>
                {data.canais.map(c => (
                  <td key={c} style={{ padding: "6px", textAlign: "center" }}>
                    <input type="checkbox"
                      checked={data.matriz[t][c]?.ativo || false}
                      onChange={(e) => toggle(t, c, e.target.checked)} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function defaultDestino(canal) {
  if (canal === "telegram") return '{"bot_token":"","chat_id":""}';
  if (canal === "email") return '{"to":"seuemail@dominio.com"}';
  if (canal === "whatsapp") return '{"numero":"5521999999999","provider":"zapi"}';
  return "{}";
}
