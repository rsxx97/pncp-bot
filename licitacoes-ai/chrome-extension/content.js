/**
 * Content Script — roda dentro das páginas do ComprasGov
 * Extrai dados de pregões (lances, chat, classificação, propostas)
 * e envia para o dashboard Licitações AI via API local.
 */

const DASHBOARD_API = "https://pncp-bot-production.up.railway.app/api";
let lastData = null;
let observerActive = false;
let pollInterval = null;

// ── Detecta qual página estamos ──
function detectarPagina() {
  const url = window.location.href;
  if (url.includes("acompanhamento-compra")) return "acompanhamento";
  if (url.includes("/compras") && !url.includes("acompanhamento")) return "lista";
  return "outro";
}

// ── Extrai dados da página de acompanhamento ──
function extrairDadosAcompanhamento() {
  const dados = {
    tipo: "acompanhamento",
    url: window.location.href,
    timestamp: new Date().toISOString(),
    compra_id: null,
    status: null,
    itens: [],
    lances: [],
    mensagens: [],
    classificacao: [],
    propostas: [],
    eventos: [],
  };

  // Extrai compra_id da URL
  const urlParams = new URLSearchParams(window.location.search);
  dados.compra_id = urlParams.get("compra");

  // Status do pregão
  const statusEls = document.querySelectorAll('[class*="situacao"], [class*="status"], [class*="etapa"]');
  statusEls.forEach(el => {
    const text = el.textContent.trim();
    if (text && text.length < 100) dados.status = text;
  });

  // ── Extrai tabelas ──
  document.querySelectorAll("table").forEach(table => {
    const headers = Array.from(table.querySelectorAll("th")).map(th => th.textContent.trim().toLowerCase());
    const rows = Array.from(table.querySelectorAll("tbody tr"));

    // Detecta tipo de tabela pelos headers
    const isLances = headers.some(h => h.includes("lance") || h.includes("rodada"));
    const isClassificacao = headers.some(h => h.includes("classific") || h.includes("colocação") || h.includes("posição"));
    const isPropostas = headers.some(h => h.includes("proposta") || h.includes("fornecedor") && h.includes("valor"));

    rows.forEach((row, idx) => {
      const cells = Array.from(row.querySelectorAll("td")).map(td => td.textContent.trim());
      if (cells.length < 2) return;

      if (isLances) {
        dados.lances.push({
          rodada: cells[0] || "",
          empresa: cells[1] || "",
          valor: parseValor(cells[2] || cells[1]),
          horario: cells[3] || cells[cells.length - 1] || "",
          raw: cells,
        });
      } else if (isClassificacao) {
        dados.classificacao.push({
          posicao: parseInt(cells[0]) || idx + 1,
          empresa: cells[1] || "",
          cnpj: extrairCNPJ(cells.join(" ")),
          valor_lance_final: parseValor(cells[2] || ""),
          habilitado: !cells.join(" ").toLowerCase().includes("inabil"),
          raw: cells,
        });
      } else if (isPropostas) {
        dados.propostas.push({
          empresa: cells[0] || "",
          cnpj: extrairCNPJ(cells.join(" ")),
          valor: parseValor(cells[1] || cells[2] || ""),
          raw: cells,
        });
      }
    });
  });

  // ── Extrai mensagens do chat ──
  const chatContainers = document.querySelectorAll(
    '[class*="mensagem"], [class*="chat"], [class*="msg"], [class*="timeline"], [class*="evento"]'
  );
  chatContainers.forEach(container => {
    const text = container.textContent.trim();
    if (text.length > 5 && text.length < 2000) {
      // Tenta separar remetente e mensagem
      const match = text.match(/^(Pregoeiro|Sistema|Fornecedor[^:]*)[:\s]+(.+)/is);
      dados.mensagens.push({
        remetente: match ? match[1].trim() : "sistema",
        mensagem: match ? match[2].trim() : text,
        horario: extrairHorario(text),
      });
    }
  });

  // ── Fallback: extrai do texto completo ──
  if (dados.classificacao.length === 0 && dados.lances.length === 0) {
    const bodyText = document.body.innerText;

    // Tenta encontrar padrão: CNPJ - Empresa - Valor
    const empresaPattern = /(\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2})\s*[-–]\s*([A-ZÀ-Ú][^R$\n]{3,50}?)\s*R?\$\s*([\d.,]+)/g;
    let match;
    let pos = 1;
    while ((match = empresaPattern.exec(bodyText)) !== null) {
      dados.classificacao.push({
        posicao: pos++,
        cnpj: match[1],
        empresa: match[2].trim(),
        valor_lance_final: parseValor(match[3]),
        habilitado: true,
      });
    }
  }

  return dados;
}

// ── Extrai dados da lista de compras ──
function extrairDadosLista() {
  const dados = {
    tipo: "lista",
    url: window.location.href,
    timestamp: new Date().toISOString(),
    compras: [],
  };

  // Cada compra na lista
  document.querySelectorAll('[class*="compra-item"], [class*="card-compra"], tr, [class*="resultado"]').forEach(el => {
    const text = el.textContent.trim();

    // Tenta extrair UASG e número
    const pregaoMatch = text.match(/PREGÃO\s+ELETRÔNICO\s+N[°º]?\s*([\d/]+)/i);
    const uasgMatch = text.match(/(\d{6})\s*[-–]\s/);
    const statusMatch = text.match(/(Em andamento|Seleção de fornecedores|Finalizada|Suspensa|Revogada|Aberta)/i);

    if (pregaoMatch) {
      dados.compras.push({
        pregao: pregaoMatch[1],
        uasg: uasgMatch ? uasgMatch[1] : "",
        status: statusMatch ? statusMatch[1] : "",
        texto: text.substring(0, 200),
      });
    }
  });

  return dados;
}

// ── Utilitários ──
function parseValor(str) {
  if (!str) return null;
  const clean = str.replace(/[R$\s]/g, "").replace(/\./g, "").replace(",", ".");
  const num = parseFloat(clean);
  return isNaN(num) ? null : num;
}

function extrairCNPJ(text) {
  const match = text.match(/\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}/);
  return match ? match[0] : null;
}

function extrairHorario(text) {
  const match = text.match(/\d{2}:\d{2}(:\d{2})?/);
  return match ? match[0] : null;
}

// ── Envia dados para o dashboard ──
async function enviarParaDashboard(dados) {
  try {
    const resp = await fetch(`${DASHBOARD_API}/pregoes/comprasgov/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados),
    });
    if (resp.ok) {
      const result = await resp.json();
      console.log("[LicitacoesAI] Dados enviados:", result);
      notificarExtensao("sync_ok", { count: dados.classificacao?.length || dados.lances?.length || 0 });
      return true;
    } else {
      console.warn("[LicitacoesAI] Erro ao enviar:", resp.status);
      return false;
    }
  } catch (e) {
    console.warn("[LicitacoesAI] Dashboard offline ou erro:", e.message);
    return false;
  }
}

// ── Notifica a extensão (popup/background) ──
function notificarExtensao(tipo, dados) {
  chrome.runtime.sendMessage({ type: tipo, data: dados });
}

// ── Observer: detecta mudanças na página ──
function iniciarObserver() {
  if (observerActive) return;

  const observer = new MutationObserver(mutations => {
    // Debounce: espera 2s após última mudança
    clearTimeout(window._licitacoesDebounce);
    window._licitacoesDebounce = setTimeout(() => {
      const pagina = detectarPagina();
      let dados;

      if (pagina === "acompanhamento") {
        dados = extrairDadosAcompanhamento();
      } else if (pagina === "lista") {
        dados = extrairDadosLista();
      }

      if (dados) {
        const dataStr = JSON.stringify(dados);
        if (dataStr !== lastData) {
          lastData = dataStr;
          enviarParaDashboard(dados);
          chrome.storage.local.set({ lastCapture: dados });
        }
      }
    }, 2000);
  });

  observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  observerActive = true;
  console.log("[LicitacoesAI] Observer ativado");
}

// ── Polling: captura periódica ──
function iniciarPolling(intervaloMs = 10000) {
  if (pollInterval) clearInterval(pollInterval);

  pollInterval = setInterval(() => {
    const pagina = detectarPagina();
    let dados;

    if (pagina === "acompanhamento") {
      dados = extrairDadosAcompanhamento();
    } else if (pagina === "lista") {
      dados = extrairDadosLista();
    }

    if (dados) {
      const dataStr = JSON.stringify(dados);
      if (dataStr !== lastData) {
        lastData = dataStr;
        enviarParaDashboard(dados);
        chrome.storage.local.set({ lastCapture: dados });
      }
    }
  }, intervaloMs);

  console.log(`[LicitacoesAI] Polling ativado: ${intervaloMs / 1000}s`);
}

// ── Mensagens do popup/background ──
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "capturar_agora") {
    const pagina = detectarPagina();
    let dados;
    if (pagina === "acompanhamento") dados = extrairDadosAcompanhamento();
    else if (pagina === "lista") dados = extrairDadosLista();

    if (dados) {
      enviarParaDashboard(dados);
      chrome.storage.local.set({ lastCapture: dados });
      sendResponse({ ok: true, dados });
    } else {
      sendResponse({ ok: false, erro: "Página não reconhecida" });
    }
  }

  if (msg.type === "get_status") {
    sendResponse({
      pagina: detectarPagina(),
      observerActive,
      polling: !!pollInterval,
      url: window.location.href,
    });
  }

  return true;
});

// ── Inicialização ──
console.log("[LicitacoesAI] Extension carregada no ComprasGov");
iniciarObserver();
iniciarPolling(15000); // A cada 15 segundos

// Captura imediata
setTimeout(() => {
  const pagina = detectarPagina();
  if (pagina === "acompanhamento" || pagina === "lista") {
    const dados = pagina === "acompanhamento" ? extrairDadosAcompanhamento() : extrairDadosLista();
    if (dados) {
      enviarParaDashboard(dados);
      chrome.storage.local.set({ lastCapture: dados });
    }
  }
}, 3000);
