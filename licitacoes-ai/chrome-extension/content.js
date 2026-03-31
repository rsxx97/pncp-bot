/**
 * Content Script Multi-Portal — Licitações AI
 * Detecta automaticamente o portal e extrai dados de pregões.
 * Portais suportados: ComprasGov, SIGA, ComprasRJ, Licitações-e, BLL, Portal Compras Públicas
 */

const DASHBOARD_API = "https://pncp-bot-production.up.railway.app/api";
let lastData = null;
let observerActive = false;
let pollInterval = null;

// ══════════════════════════════════════════════
// DETECÇÃO DE PORTAL
// ══════════════════════════════════════════════

function detectarPortal() {
  const url = window.location.href.toLowerCase();
  const host = window.location.hostname.toLowerCase();

  if (host.includes("estaleiro.serpro.gov.br") || host.includes("comprasnet") || host.includes("compras.gov"))
    return "comprasgov";
  if (host.includes("siga") || url.includes("siga.fazenda") || host.includes("licitacao.rj.gov.br"))
    return "siga";
  if (host.includes("compras.rj.gov.br"))
    return "comprasrj";
  if (host.includes("licitacoes-e") || host.includes("licitacoese") || host.includes("bb.com.br"))
    return "licitacoes-e";
  if (host.includes("bll") || host.includes("bllcompras"))
    return "bll";
  if (host.includes("portaldecompraspublicas"))
    return "portalcompras";
  return "desconhecido";
}

function detectarPagina() {
  const url = window.location.href;
  if (url.includes("acompanhamento") || url.includes("disputa") || url.includes("sessao") || url.includes("lance"))
    return "acompanhamento";
  if (url.includes("resultado") || url.includes("ata") || url.includes("classificacao"))
    return "resultado";
  if (url.includes("compras") || url.includes("licitacao") || url.includes("pregao") || url.includes("edital"))
    return "lista";
  return "outro";
}

// ══════════════════════════════════════════════
// EXTRATOR GENÉRICO (funciona em qualquer portal)
// ══════════════════════════════════════════════

function extrairDadosGenericos() {
  const dados = {
    portal: detectarPortal(),
    tipo: detectarPagina(),
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

  const bodyText = document.body.innerText;

  // Extrai CNPJ + Empresa + Valor (padrão universal)
  const cnpjPattern = /(\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\/\s]?\d{4}[-\s]?\d{2})\s*[-–\s]*([A-ZÀ-Ú][^R$\n]{3,60}?)\s*(?:R?\$\s*|Valor[^:]*:\s*R?\$\s*)([\d.,]+)/g;
  let match;
  let pos = 1;
  while ((match = cnpjPattern.exec(bodyText)) !== null) {
    const cnpj = match[1].replace(/[^\d\/\.\-]/g, "");
    const empresa = match[2].trim();
    const valor = parseValor(match[3]);
    if (valor && valor > 1000) {
      dados.classificacao.push({
        posicao: pos++,
        cnpj,
        empresa,
        valor_lance_final: valor,
        habilitado: true,
      });
    }
  }

  // Extrai de tabelas
  document.querySelectorAll("table").forEach(table => {
    const headers = Array.from(table.querySelectorAll("th")).map(th => th.textContent.trim().toLowerCase());
    const rows = Array.from(table.querySelectorAll("tbody tr, tr")).slice(1);

    const isLances = headers.some(h => h.includes("lance") || h.includes("rodada") || h.includes("valor ofertado"));
    const isClassif = headers.some(h => h.includes("classific") || h.includes("colocação") || h.includes("posição") || h.includes("fornecedor"));
    const isPropostas = headers.some(h => (h.includes("proposta") || h.includes("empresa")) && headers.some(h2 => h2.includes("valor")));

    rows.forEach((row, idx) => {
      const cells = Array.from(row.querySelectorAll("td")).map(td => td.textContent.trim());
      if (cells.length < 2) return;

      if (isLances) {
        dados.lances.push({
          rodada: cells[0] || "",
          empresa: cells[1] || "",
          valor: parseValor(cells[2] || cells[1]),
          horario: cells[cells.length - 1] || "",
        });
      } else if (isClassif) {
        dados.classificacao.push({
          posicao: parseInt(cells[0]) || idx + 1,
          empresa: cells[1] || "",
          cnpj: extrairCNPJ(cells.join(" ")),
          valor_lance_final: parseValor(cells[2] || cells[3] || ""),
          habilitado: !cells.join(" ").toLowerCase().includes("inabil"),
        });
      } else if (isPropostas) {
        dados.propostas.push({
          empresa: cells[0] || "",
          cnpj: extrairCNPJ(cells.join(" ")),
          valor: parseValor(cells[1] || cells[2] || ""),
        });
      }
    });
  });

  // Mensagens do chat/pregoeiro
  document.querySelectorAll('[class*="mensagem"], [class*="chat"], [class*="msg"], [class*="timeline"], [class*="evento"], [class*="aviso"]').forEach(el => {
    const text = el.textContent.trim();
    if (text.length > 5 && text.length < 2000) {
      const match = text.match(/^(Pregoeiro|Sistema|Fornecedor[^:]*|Autoridade[^:]*)[:\s]+(.+)/is);
      dados.mensagens.push({
        remetente: match ? match[1].trim() : "sistema",
        mensagem: match ? match[2].trim() : text,
        horario: extrairHorario(text),
      });
    }
  });

  return dados;
}

// ══════════════════════════════════════════════
// EXTRATOR COMPRASGOV (ComprasNet/Compras.gov.br)
// ══════════════════════════════════════════════

function extrairComprasGov() {
  const dados = extrairDadosGenericos();
  dados.portal = "comprasgov";

  const urlParams = new URLSearchParams(window.location.search);
  dados.compra_id = urlParams.get("compra");
  dados.title = document.title;
  dados.titulo = document.body.innerText.substring(0, 500);

  // Método 1: Busca por blocos CNPJ + Nome + Valor no texto completo
  if (dados.classificacao.length === 0) {
    const bodyText = document.body.innerText;

    // Encontra todos os blocos CNPJ...R$ no texto
    // Formato: "CNPJ [badges] [status] EMPRESA UF Valor ofertado ... R$ X.XXX,XX"
    const blocos = bodyText.split(/(?=\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2})/);
    let pos = 1;
    for (const bloco of blocos) {
      const cnpjMatch = bloco.match(/^(\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2})/);
      if (!cnpjMatch) continue;
      const cnpj = cnpjMatch[1];

      // Extrai valor (primeiro R$ no bloco)
      const valorMatch = bloco.match(/R\$\s*([\d.,]+)/);
      if (!valorMatch) continue;
      const valor = parseValor(valorMatch[1]);
      if (!valor || valor < 100) continue;

      // Extrai status (Inabilitada, Desclassificada, Aceita e habilitada, etc.)
      const habMatch = bloco.match(/(Inabilitada|Desclassificada|Aceita e habilitada|Aceita)/i);
      const habilitado = !habMatch || habMatch[1].toLowerCase().includes("aceita");

      // Extrai nome da empresa (texto em maiúsculas entre status/badges e UF)
      const nomeMatch = bloco.match(/(?:Inabilitada|Desclassificada|Aceita e habilitada|Aceita|integridade)\s+([A-ZÀ-Ú0-9][A-ZÀ-Ú0-9\s\.\-\/&,]+?)\s+[A-Z]{2}\s+Valor/);
      let empresa = nomeMatch ? nomeMatch[1].trim() : "";

      // Fallback: pega texto entre CNPJ e "Valor"
      if (!empresa) {
        const fallback = bloco.match(/\d{2}\s+(.+?)\s+[A-Z]{2}\s+Valor/);
        if (fallback) empresa = fallback[1].replace(/ME\/EPP|Programa de integridade|Equidade[^A-Z]*/g, "").trim();
      }

      if (empresa) {
        dados.classificacao.push({ posicao: pos++, cnpj, empresa: empresa.substring(0, 80), valor_lance_final: valor, habilitado });
      }
    }

    // Método 2: Se não achou com padrão complexo, tenta simples
    if (dados.classificacao.length === 0) {
      const cnpjRegex = /(\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2})/g;
      const valorRegex = /R\$\s*([\d.,]+)/g;
      const cnpjs = [...bodyText.matchAll(cnpjRegex)];
      const valores = [...bodyText.matchAll(valorRegex)];

      if (cnpjs.length > 0 && cnpjs.length <= valores.length) {
        const lines = bodyText.split("\n");
        let pos = 1;

        for (const cnpjMatch of cnpjs) {
          const cnpj = cnpjMatch[1];
          const idx = cnpjMatch.index;
          // Pega texto depois do CNPJ até o próximo CNPJ ou 500 chars
          const afterCnpj = bodyText.substring(idx + cnpj.length, idx + 500);

          // Nome: primeira sequência de palavras maiúsculas após CNPJ
          const nomeMatch = afterCnpj.match(/\s*([A-ZÀ-Ú][A-ZÀ-Ú\s\.\-\/&,]{5,80})/);
          const empresa = nomeMatch ? nomeMatch[1].trim() : "";

          // Valor: primeiro R$ após o nome
          const valorMatch = afterCnpj.match(/R\$\s*([\d.,]+)/);
          const valor = valorMatch ? parseValor(valorMatch[1]) : null;

          if (empresa && valor && valor > 100) {
            // Evita duplicatas
            if (!dados.classificacao.find(c => c.cnpj === cnpj)) {
              dados.classificacao.push({ posicao: pos++, cnpj, empresa, valor_lance_final: valor, habilitado: true });
            }
          }
        }
      }
    }
  }

  return dados;
}

// ══════════════════════════════════════════════
// EXTRATOR SIGA (Estado RJ)
// ══════════════════════════════════════════════

function extrairSIGA() {
  const dados = extrairDadosGenericos();
  dados.portal = "siga";

  // SIGA usa tabelas HTML padrão para lances e classificação
  // Tenta extrair número do pregão da URL ou título
  const titulo = document.title || "";
  const pregaoMatch = titulo.match(/(\d+\/\d{4})/);
  if (pregaoMatch) dados.compra_id = pregaoMatch[1];

  return dados;
}

// ══════════════════════════════════════════════
// EXTRATOR COMPRASRJ (Estado RJ)
// ══════════════════════════════════════════════

function extrairComprasRJ() {
  const dados = extrairDadosGenericos();
  dados.portal = "comprasrj";

  // ComprasRJ usa .action pages com tabelas padrão
  const urlMatch = window.location.href.match(/id=(\d+)/);
  if (urlMatch) dados.compra_id = urlMatch[1];

  return dados;
}

// ══════════════════════════════════════════════
// EXTRATOR LICITAÇÕES-E (Banco do Brasil)
// ══════════════════════════════════════════════

function extrairLicitacoesE() {
  const dados = extrairDadosGenericos();
  dados.portal = "licitacoes-e";

  // Licitações-e usa iframes e Java applets
  const urlMatch = window.location.href.match(/idLicitacao=(\d+)/);
  if (urlMatch) dados.compra_id = urlMatch[1];

  // Tenta extrair de dentro de iframes
  document.querySelectorAll("iframe").forEach(iframe => {
    try {
      const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
      if (iframeDoc) {
        iframeDoc.querySelectorAll("table tr").forEach((row, idx) => {
          const cells = Array.from(row.querySelectorAll("td")).map(td => td.textContent.trim());
          if (cells.length >= 3) {
            const cnpj = extrairCNPJ(cells.join(" "));
            const valor = parseValor(cells.find(c => c.match(/[\d.,]+/)) || "");
            if (cnpj && valor) {
              dados.classificacao.push({ posicao: idx + 1, cnpj, empresa: cells[0] || cells[1], valor_lance_final: valor, habilitado: true });
            }
          }
        });
      }
    } catch (e) { /* cross-origin blocked */ }
  });

  return dados;
}

// ══════════════════════════════════════════════
// EXTRATOR BLL/ComprasBR
// ══════════════════════════════════════════════

function extrairBLL() {
  const dados = extrairDadosGenericos();
  dados.portal = "bll";

  const urlMatch = window.location.href.match(/Process\/(\d+)/i);
  if (urlMatch) dados.compra_id = urlMatch[1];

  return dados;
}

// ══════════════════════════════════════════════
// EXTRATOR PORTAL COMPRAS PÚBLICAS
// ══════════════════════════════════════════════

function extrairPortalCompras() {
  const dados = extrairDadosGenericos();
  dados.portal = "portalcompras";

  const urlMatch = window.location.href.match(/\/(\d+)(?:\?|$)/);
  if (urlMatch) dados.compra_id = urlMatch[1];

  return dados;
}

// ══════════════════════════════════════════════
// UTILITÁRIOS
// ══════════════════════════════════════════════

function parseValor(str) {
  if (!str) return null;
  const clean = str.replace(/[R$\s]/g, "").replace(/\./g, "").replace(",", ".");
  const num = parseFloat(clean);
  return isNaN(num) ? null : num;
}

function extrairCNPJ(text) {
  const match = text.match(/\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\/\s]?\d{4}[-\s]?\d{2}/);
  return match ? match[0] : null;
}

function extrairHorario(text) {
  const match = text.match(/\d{2}:\d{2}(:\d{2})?/);
  return match ? match[0] : null;
}

// ══════════════════════════════════════════════
// ROTEADOR: escolhe extrator pelo portal
// ══════════════════════════════════════════════

function extrairDados() {
  const portal = detectarPortal();
  switch (portal) {
    case "comprasgov": return extrairComprasGov();
    case "siga": return extrairSIGA();
    case "comprasrj": return extrairComprasRJ();
    case "licitacoes-e": return extrairLicitacoesE();
    case "bll": return extrairBLL();
    case "portalcompras": return extrairPortalCompras();
    default: return extrairDadosGenericos();
  }
}

// ══════════════════════════════════════════════
// ENVIO PARA DASHBOARD
// ══════════════════════════════════════════════

async function enviarParaDashboard(dados) {
  // Envia via background.js para evitar CORS
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: "enviar_dados", data: dados }, (response) => {
      if (response?.ok) {
        console.log(`[LicitacoesAI][${dados.portal}] Dados enviados via background:`, response.result);
        resolve(true);
      } else {
        console.warn(`[LicitacoesAI][${dados.portal}] Erro:`, response?.error || "sem resposta");
        resolve(false);
      }
    });
  });
}

function notificarExtensao(tipo, dados) {
  try { chrome.runtime.sendMessage({ type: tipo, data: dados }); } catch (e) { }
}

// ══════════════════════════════════════════════
// OBSERVER + POLLING
// ══════════════════════════════════════════════

function iniciarObserver() {
  if (observerActive) return;
  const observer = new MutationObserver(() => {
    clearTimeout(window._licitacoesDebounce);
    window._licitacoesDebounce = setTimeout(() => {
      const dados = extrairDados();
      if (dados && (dados.classificacao.length || dados.lances.length || dados.mensagens.length)) {
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
}

function iniciarPolling(intervaloMs = 15000) {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(() => {
    const dados = extrairDados();
    if (dados && (dados.classificacao.length || dados.lances.length || dados.mensagens.length)) {
      const dataStr = JSON.stringify(dados);
      if (dataStr !== lastData) {
        lastData = dataStr;
        enviarParaDashboard(dados);
        chrome.storage.local.set({ lastCapture: dados });
      }
    }
  }, intervaloMs);
}

// ══════════════════════════════════════════════
// MENSAGENS DO POPUP/BACKGROUND
// ══════════════════════════════════════════════

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "capturar_agora") {
    const dados = extrairDados();
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
      portal: detectarPortal(),
      pagina: detectarPagina(),
      observerActive,
      polling: !!pollInterval,
      url: window.location.href,
    });
  }
  return true;
});

// ══════════════════════════════════════════════
// INICIALIZAÇÃO
// ══════════════════════════════════════════════

const portal = detectarPortal();
console.log(`[LicitacoesAI] Extensão carregada — Portal: ${portal} | Página: ${detectarPagina()}`);
iniciarObserver();
iniciarPolling(15000);

// Captura imediata após 3s (espera página carregar)
setTimeout(() => {
  const dados = extrairDados();
  if (dados && (dados.classificacao.length || dados.lances.length || dados.propostas.length)) {
    enviarParaDashboard(dados);
    chrome.storage.local.set({ lastCapture: dados });
  }
}, 3000);
