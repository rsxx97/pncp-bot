import { useEffect, useState } from "react";
import { radarApi } from "./api";

export default function CredenciaisPage() {
  const [credenciais, setCredenciais] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [captcha, setCaptcha] = useState(null);
  const [testando, setTestando] = useState(false);
  const [resultadoTeste, setResultadoTeste] = useState(null);

  const carregar = async () => {
    setLoading(true);
    const token = localStorage.getItem("token");
    const [credR, capR] = await Promise.all([
      fetch("/api/radar/credenciais", { headers: token ? { Authorization: `Bearer ${token}` } : {} }),
      fetch("/api/radar/captcha/status", { headers: token ? { Authorization: `Bearer ${token}` } : {} }),
    ]);
    if (credR.ok) setCredenciais(await credR.json());
    if (capR.ok) setCaptcha(await capR.json());
    setLoading(false);
  };

  const testarConexao = async () => {
    setTestando(true);
    setResultadoTeste(null);
    try {
      const r = await radarApi.testarCredencial();
      setResultadoTeste(r);
    } catch (e) {
      setResultadoTeste({ ok: false, erro: e.message });
    }
    setTestando(false);
  };

  useEffect(() => { carregar(); }, []);

  const deletar = async (slug) => {
    if (!confirm(`Remover credencial do ${slug}?`)) return;
    const token = localStorage.getItem("token");
    await fetch(`/api/radar/credenciais/${slug}`, {
      method: "DELETE",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    carregar();
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: "#EEEEE8" }}>
          Credenciais de Portais
        </h2>
        <button onClick={() => setShowUpload(true)}
          style={{
            padding: "8px 16px", background: "#BEFF3A", color: "#1A1A18",
            border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 700,
          }}>
          + Conectar Portal
        </button>
      </div>

      <div style={{ fontSize: 12, color: "#98968E", marginBottom: 16, lineHeight: 1.6 }}>
        Conecte o Compras.gov.br (ou outros portais) usando o certificado digital A1 (.pfx) da empresa.
        O radar usa o cert pra puxar lances, mensagens do pregoeiro e sua posição em tempo real,
        igual ao eLicita/Effecti. O arquivo fica cifrado no banco — você pode remover a qualquer momento.
      </div>

      {/* Status do 2captcha */}
      {captcha && (
        <div style={{
          padding: 12, marginBottom: 20, borderRadius: 8,
          background: captcha.configured ? "rgba(34,197,94,0.1)" : "rgba(220,38,38,0.1)",
          border: `1px solid ${captcha.configured ? "#16A34A" : "#DC2626"}`,
          fontSize: 12, color: captcha.configured ? "#16A34A" : "#DC2626",
        }}>
          {captcha.configured ? (
            <>
              <b>✓ Solver hCaptcha configurado</b> (provider: {captcha.provider}).
              Login automático no SERPRO funcionando. Cliente sobe o .pfx e mensagens fluem sem interação.
            </>
          ) : (
            <>
              <b>⚠ 2captcha NÃO configurado</b> — sem ele, o login automático no ComprasNet falha (gov.br exige hCaptcha).
              Configure a variável <code>TWOCAPTCHA_API_KEY</code> no <code>.env</code>.
              Cadastre-se em <a href="https://2captcha.com" target="_blank" style={{ color: "#DC2626", textDecoration: "underline" }}>2captcha.com</a>
              (~R$ 0,03 por captcha — ~R$ 50/mês para uso moderado).
            </>
          )}
        </div>
      )}

      {/* Botão Testar Conexão */}
      {credenciais.length > 0 && (
        <div style={{ marginBottom: 18, padding: 14, background: "#111114", border: "1px solid #2A2A32", borderRadius: 8 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 14 }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#EEEEE8" }}>Testar conexão isolada</div>
              <div style={{ fontSize: 11, color: "#98968E", marginTop: 2 }}>
                Faz 1 login com o .pfx e mostra o resultado, sem afetar os pregões monitorados. Use depois de trocar IP ou atualizar cert.
              </div>
            </div>
            <button onClick={testarConexao} disabled={testando}
              style={{
                padding: "8px 14px", background: testando ? "#5A5854" : "#5A9EF7", color: "#fff",
                border: 0, borderRadius: 6, cursor: testando ? "wait" : "pointer", fontSize: 12, fontWeight: 700, fontFamily: "monospace",
                whiteSpace: "nowrap",
              }}>
              {testando ? "TESTANDO..." : "TESTAR CONEXÃO"}
            </button>
          </div>
          {resultadoTeste && (
            <div style={{
              marginTop: 12, padding: 10, borderRadius: 6,
              background: resultadoTeste.ok ? "rgba(34,197,94,0.1)" : "rgba(220,38,38,0.1)",
              border: `1px solid ${resultadoTeste.ok ? "#16A34A" : "#DC2626"}`,
              fontSize: 11, color: resultadoTeste.ok ? "#34D399" : "#F87171",
              fontFamily: "monospace",
            }}>
              {resultadoTeste.ok ? (
                <>
                  <b>✓ Conexão OK</b> em {resultadoTeste.duracao_seg}s · {resultadoTeste.cookies_total} cookies ({resultadoTeste.cookies_cnetmobile} cnetmobile)
                  <div style={{ color: "#98968E", marginTop: 4, fontSize: 10 }}>URL final: {resultadoTeste.url_final}</div>
                </>
              ) : (
                <>
                  <b>✗ Falhou em fase: {resultadoTeste.fase || "desconhecida"}</b> ({resultadoTeste.duracao_seg}s)
                  <div style={{ marginTop: 4, fontSize: 10 }}>{resultadoTeste.erro}</div>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {loading && <div style={{ color: "#5A5854", fontSize: 12 }}>Carregando…</div>}

      {!loading && credenciais.length === 0 && (
        <div style={{ padding: 40, textAlign: "center", color: "#5A5854", fontSize: 12, background: "#18181C", borderRadius: 8 }}>
          Nenhuma credencial cadastrada ainda. Clique em <b style={{ color: "#BEFF3A" }}>+ Conectar Portal</b>.
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 12 }}>
        {credenciais.map(c => (
          <div key={c.slug} style={{
            padding: 16, background: "#18181C", borderRadius: 8, border: "1px solid #2A2A32",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: "#EEEEE8" }}>{c.nome}</div>
                <div style={{ fontSize: 10, color: "#5A5854", fontFamily: "monospace", marginTop: 2 }}>{c.slug}</div>
              </div>
              <span style={{
                fontSize: 10, padding: "2px 8px", borderRadius: 4,
                background: c.status === "ok" ? "#1b653b" : "#611316",
                color: "#fff", fontWeight: 700, textTransform: "uppercase",
              }}>
                {c.status}
              </span>
            </div>
            <div style={{ fontSize: 11, color: "#98968E", marginBottom: 12 }}>
              Conectado em {c.criado_em ? new Date(c.criado_em).toLocaleDateString("pt-BR") : "-"}
            </div>
            <button onClick={() => deletar(c.slug)}
              style={{
                padding: "4px 10px", fontSize: 10, background: "transparent",
                color: "#DC2626", border: "1px solid #DC2626", borderRadius: 4, cursor: "pointer",
              }}>
              Remover
            </button>
          </div>
        ))}
      </div>

      {showUpload && (
        <ModalUploadPfx onClose={() => setShowUpload(false)} onSalvo={() => { setShowUpload(false); carregar(); }} />
      )}
    </div>
  );
}

function ModalUploadPfx({ onClose, onSalvo }) {
  const [arquivo, setArquivo] = useState(null);
  const [senha, setSenha] = useState("");
  const [portal, setPortal] = useState("comprasnet");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  const [resultado, setResultado] = useState(null);

  const salvar = async () => {
    if (!arquivo) return setErro("Selecione o arquivo .pfx");
    if (!senha) return setErro("Digite a senha do certificado");
    setSalvando(true); setErro("");

    const fd = new FormData();
    fd.append("arquivo", arquivo);
    fd.append("senha", senha);
    fd.append("portal_slug", portal);

    const token = localStorage.getItem("token");
    try {
      const r = await fetch("/api/radar/credenciais/pfx", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${r.status}`);
      }
      const data = await r.json();
      setResultado(data);
    } catch (e) {
      setErro(e.message);
    }
    setSalvando(false);
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200 }}>
      <div style={{ background: "#FFF", color: "#1A1A18", padding: 24, borderRadius: 12, width: 520, maxWidth: "90vw" }}>
        {!resultado ? (
          <>
            <h3 style={{ margin: "0 0 4px", fontSize: 16, fontWeight: 700 }}>Conectar portal via certificado digital</h3>
            <p style={{ margin: "0 0 16px", fontSize: 12, color: "#6B7280" }}>
              Faça upload do certificado A1 (.pfx) que sua empresa usa pra enviar propostas. O arquivo fica cifrado e nunca é exposto.
            </p>

            <label style={{ fontSize: 11, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>Portal</label>
            <select value={portal} onChange={e => setPortal(e.target.value)}
              style={{ width: "100%", padding: "8px 10px", fontSize: 13, marginBottom: 12, border: "1px solid #D1D5DB", borderRadius: 6 }}>
              <option value="comprasnet">Compras.gov.br (ComprasNet)</option>
            </select>

            <label style={{ fontSize: 11, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>Arquivo .pfx</label>
            <input type="file" accept=".pfx,.p12"
              onChange={e => setArquivo(e.target.files?.[0] || null)}
              style={{ width: "100%", padding: "8px 10px", fontSize: 13, marginBottom: 12, border: "1px solid #D1D5DB", borderRadius: 6 }} />

            <label style={{ fontSize: 11, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>Senha do certificado</label>
            <input type="password" value={senha} onChange={e => setSenha(e.target.value)}
              placeholder="Senha que você usa pra assinar"
              style={{ width: "100%", padding: "8px 10px", fontSize: 13, marginBottom: 16, border: "1px solid #D1D5DB", borderRadius: 6 }} />

            {erro && <div style={{ color: "#DC2626", fontSize: 12, marginBottom: 12 }}>{erro}</div>}

            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button onClick={onClose}
                style={{ padding: "8px 16px", background: "#F3F4F6", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12 }}>
                Cancelar
              </button>
              <button onClick={salvar} disabled={salvando}
                style={{ padding: "8px 16px", background: "#1A1A18", color: "#FFF", border: "none", borderRadius: 6, cursor: salvando ? "wait" : "pointer", fontSize: 12, fontWeight: 600 }}>
                {salvando ? "Validando…" : "Conectar"}
              </button>
            </div>
          </>
        ) : (
          <>
            <h3 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700, color: "#1b653b" }}>✓ Certificado validado</h3>

            <div style={{ background: "#F3F4F6", borderRadius: 8, padding: 12, marginBottom: 16 }}>
              <Linha label="Titular" valor={resultado.nome_titular || "-"} />
              <Linha label="CNPJ" valor={resultado.cnpj || "-"} />
              <Linha label="Emissor" valor={resultado.emissor || "-"} />
              <Linha label="Válido até" valor={new Date(resultado.validade_ate).toLocaleDateString("pt-BR")} />
              <Linha label="Dias para vencer" valor={resultado.dias_para_vencer} />
            </div>

            <p style={{ fontSize: 12, color: "#6B7280", marginBottom: 16 }}>
              A partir de agora o radar vai puxar lances, mensagens do pregoeiro e sua posição em tempo real
              nos pregões em que esse CNPJ estiver participando.
            </p>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button onClick={onSalvo}
                style={{ padding: "8px 16px", background: "#1b653b", color: "#FFF", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
                Concluir
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Linha({ label, valor }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "4px 0" }}>
      <span style={{ color: "#6B7280" }}>{label}</span>
      <span style={{ fontWeight: 600, color: "#1A1A18", fontFamily: "monospace" }}>{valor}</span>
    </div>
  );
}
