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
  gerarPlanilha: (pncpId, empresa) => {
    const body = empresa ? JSON.stringify({ empresa }) : undefined;
    return request(`/api/editais/${pncpId}/planilha`, { method: 'POST', body });
  },
  getEmpresas: () => request('/api/editais/empresas/listar'),
  adicionarPostoManual: (pncpId, postos) => request(`/api/editais/${pncpId}/postos-manual`, { method: 'POST', body: JSON.stringify({ postos }) }),
  competitivo: (pncpId) => request(`/api/editais/${pncpId}/competitivo`, { method: 'POST' }),
  arquivar: (pncpId) => request(`/api/editais/${pncpId}/arquivar`, { method: 'POST' }),
  resetar: (pncpId) => request(`/api/editais/${pncpId}/resetar`, { method: 'POST' }),
  listarArquivos: (pncpId) => request(`/api/editais/${pncpId}/pdf/arquivos`),
  uploadPlanilha: async (pncpId, file) => {
    const form = new FormData();
    form.append('file', file);
    const resp = await fetch(`/api/editais/${pncpId}/planilha/upload`, { method: 'POST', body: form });
    if (!resp.ok) throw new Error(`Upload falhou: ${resp.status}`);
    return resp.json();
  },

  // Busca PNCP
  buscarPncp: (q, filtros = {}) => {
    const qs = new URLSearchParams({ q });
    if (filtros.uf) qs.set('uf', filtros.uf);
    if (filtros.municipio) qs.set('municipio', filtros.municipio);
    if (filtros.modalidade) qs.set('modalidade', filtros.modalidade);
    if (filtros.valor_min) qs.set('valor_min', filtros.valor_min);
    if (filtros.valor_max) qs.set('valor_max', filtros.valor_max);
    return request(`/api/editais/pncp/buscar?${qs.toString()}`);
  },
  importarPncp: (pncpIds) => request('/api/editais/pncp/importar', { method: 'POST', body: JSON.stringify({ pncp_ids: pncpIds }) }),

  // Concorrentes
  getConcorrentes: () => request('/api/concorrentes'),
  addConcorrente: (data) => request('/api/concorrentes', { method: 'POST', body: JSON.stringify(data) }),
  removeConcorrente: (cnpj) => request(`/api/concorrentes/${encodeURIComponent(cnpj)}`, { method: 'DELETE' }),
  buscarConcorrentePncp: (termo, uf = 'RJ') => request(`/api/concorrentes/buscar-pncp?termo=${encodeURIComponent(termo)}&uf=${uf}`),
  perfilConcorrente: (cnpj) => request(`/api/concorrentes/${encodeURIComponent(cnpj)}/perfil`),
  seedConcorrentes: () => request('/api/concorrentes/seed', { method: 'POST' }),

  // Config
  getConfig: () => request('/api/config'),
};
