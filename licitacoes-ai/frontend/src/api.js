const BASE = '';

async function request(url, options = {}) {
  const resp = await fetch(BASE + url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!resp.ok) throw new Error(`API ${resp.status}: ${resp.statusText}`);
  return resp.json();
}

export const api = {
  // Dashboard
  getMetrics: () => request('/api/dashboard/metrics'),
  getWeeklyChart: () => request('/api/dashboard/weekly-chart'),

  // Editais
  getEditais: (params = {}) => {
    const qs = new URLSearchParams();
    if (params.status) params.status.forEach(s => qs.append('status', s));
    if (params.page) qs.set('page', params.page);
    if (params.per_page) qs.set('per_page', params.per_page);
    if (params.sort) qs.set('sort', params.sort);
    if (params.busca) qs.set('busca', params.busca);
    return request(`/api/editais?${qs.toString()}`);
  },
  getEdital: (pncpId) => request(`/api/editais/${pncpId}`),
  analisar: (pncpId) => request(`/api/editais/${pncpId}/analisar`, { method: 'POST' }),
  gerarPlanilha: (pncpId) => request(`/api/editais/${pncpId}/planilha`, { method: 'POST' }),
  competitivo: (pncpId) => request(`/api/editais/${pncpId}/competitivo`, { method: 'POST' }),
  arquivar: (pncpId) => request(`/api/editais/${pncpId}/arquivar`, { method: 'POST' }),

  // Concorrentes
  getConcorrentes: () => request('/api/concorrentes'),

  // Config
  getConfig: () => request('/api/config'),
};
