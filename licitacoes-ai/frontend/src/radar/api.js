async function req(url, opts = {}) {
  const token = localStorage.getItem("token");
  const r = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers || {}),
    },
    ...opts,
  });
  if (!r.ok) throw new Error(`API ${r.status}: ${(await r.text()).slice(0, 200)}`);
  if (r.status === 204) return null;
  const ct = r.headers.get("content-type") || "";
  return ct.includes("application/json") ? r.json() : r.text();
}

export const radarApi = {
  listarPortais: () => req("/api/radar/portais"),
  listarPregoes: (params = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v) qs.set(k, v);
    }
    return req(`/api/radar/pregoes?${qs.toString()}`);
  },
  monitorar: (data) => req("/api/radar/pregoes", { method: "POST", body: JSON.stringify(data) }),
  desmonitorar: (id) => req(`/api/radar/pregoes/${id}`, { method: "DELETE" }),
  silenciar: (id, silenciado) => req(`/api/radar/pregoes/${id}/silenciar?silenciado=${silenciado}`, { method: "POST" }),
  favoritar: (id, favorito) => req(`/api/radar/pregoes/${id}/favorito?favorito=${favorito}`, { method: "POST" }),
  forcarTick: () => req("/api/radar/tick", { method: "POST" }),

  captchaStatus: () => req("/api/radar/captcha/status"),
  listarCredenciais: () => req("/api/radar/credenciais"),
  salvarCredencial: (d) => req("/api/radar/credenciais", { method: "PUT", body: JSON.stringify(d) }),
  deletarCredencial: (slug) => req(`/api/radar/credenciais/${slug}`, { method: "DELETE" }),
  testarCredencial: () => req("/api/radar/credenciais/testar", { method: "POST" }),

  custoCaptcha: () => req("/api/radar/custo"),
  resetCircuitBreaker: () => req("/api/radar/circuit-breaker/reset", { method: "POST" }),

  listarAlertas: () => req("/api/radar/alertas"),
  salvarAlerta: (d) => req("/api/radar/alertas", { method: "PUT", body: JSON.stringify(d) }),
  testarCanal: (d) => req("/api/radar/alertas/testar", { method: "POST", body: JSON.stringify(d) }),

  historico: (params = {}) => {
    const qs = new URLSearchParams(params);
    return req(`/api/radar/historico?${qs.toString()}`);
  },
  marcarLido: (id) => req(`/api/radar/historico/marcar-lido/${id}`, { method: "POST" }),
  marcarTodosLidos: () => req(`/api/radar/historico/marcar-todos-lidos`, { method: "POST" }),
  exportCsvUrl: (dias = 90, tipo = "") => `/api/radar/historico/export.csv?dias=${dias}${tipo ? `&tipo=${tipo}` : ""}`,
};
