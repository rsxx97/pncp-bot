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
  const dados = {
    portal: "comprasgov",
    tipo: detectarPagina(),
    url: window.location.href,
    timestamp: new Date().toISOString(),
    compra_id: new URLSearchParams(window.location.search).get("compra"),
    title: document.title,
    titulo: "",
    classificacao: [],
    lances: [],
    mensagens: [],
    propostas: [],
    eventos: [],
    nossa_empresa: "MANUTEC",
  };

  const bodyText = document.body.innerText;
  dados.titulo = bodyText.substring(0, 1000);

  // Extrai UASG e órgão
  const uasgMatch = bodyText.match(/UASG\s*(\d+)\s*-\s*([^\n]+)/);
  if (uasgMatch) {
    dados.uasg = uasgMatch[1];
    dados.orgao_nome = uasgMatch[2].trim().split(/\s+Crit/)[0].trim();
  }

  // Número do pregão
  const pregaoMatch = bodyText.match(/N[°º]?\s*(\d+\/\d{4})/);
  if (pregaoMatch) dados.numero_pregao = pregaoMatch[1];

  // Tipo de modalidade
  const modalMatch = bodyText.match(/(Pregão Eletrônico|Concorrência Eletrônica|Dispensa|Pregão)/i);
  if (modalMatch) dados.modalidade = modalMatch[1];

  // Objeto: texto após número de itens (ex: "1 Obras Civis Públicas")
  const objetoMatch = bodyText.match(/\d+\s+([A-ZÀ-Ú][a-záàâãéèêíïóôõúç\s]+(?:\([^)]+\))?)/);
  if (objetoMatch) dados.objeto = objetoMatch[1].trim();

  // PARSER DOM: usa elementos da página diretamente
  const cards = document.querySelectorAll('.cp-itens-card, .cp-item-expansivel, [class*="fornecedor-card"]');
  let pos = 1;
  let nossaPosicao = null;
  let nossoLance = null;

  if (cards.length > 0) {
    // Método DOM: cada card é um fornecedor
    cards.forEach(card => {
      const text = card.innerText;
      const cnpjMatch = text.match(/(\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2})/);
      if (!cnpjMatch) return;
      const cnpj = cnpjMatch[1];

      const valorMatch = text.match(/R\$\s*([\d.,]+)/);
      if (!valorMatch) return;
      const valor = parseValor(valorMatch[1]);
      if (!valor || valor < 100) return;

      const habilitado = !text.includes("Inabilitada") && !text.includes("Desclassificada");
      const statusText = text.includes("Inabilitada") ? "Inabilitada" : text.includes("Desclassificada") ? "Desclassificada" : text.includes("Aceita") ? "Aceita e habilitada" : "";

      // Nome: linhas do texto, pega a que parece nome de empresa
      const lines = text.split("\n").map(l => l.trim()).filter(l => l.length > 3);
      let empresa = "";
      for (const line of lines) {
        if (line.match(/^\d{2}\.\d{3}/) || line.includes("R$") || line.includes("Valor") || line.includes("ME/EPP") || line.includes("Programa") || line.includes("Equidade") || line.includes("Inabilitada") || line.includes("Desclassificada") || line.includes("Aceita") || line.length <= 3) continue;
        if (line.match(/^[A-ZÀ-Ú0-9]/) && line.length > 5 && !line.match(/^[A-Z]{2}$/)) {
          empresa = line;
          break;
        }
      }

      if (!empresa) return;

      const isNosso = empresa.toUpperCase().includes("MANUTEC") || empresa.toUpperCase().includes("MIAMI");
      if (isNosso) {
        nossaPosicao = pos;
        nossoLance = valor;
      }

      dados.classificacao.push({
        posicao: pos++, cnpj, empresa: empresa.substring(0, 100),
        valor_lance_final: valor, habilitado, status: statusText, nosso: isNosso,
      });
    });
  } else {
    // Fallback: parse por texto (split por CNPJ)
    const cnpjPattern = /\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}/g;
    const cnpjs = [];
    let m;
    while ((m = cnpjPattern.exec(bodyText)) !== null) cnpjs.push({ cnpj: m[0], index: m.index });

    for (let i = 0; i < cnpjs.length; i++) {
      const { cnpj, index: startIdx } = cnpjs[i];
      const endIdx = i + 1 < cnpjs.length ? cnpjs[i + 1].index : startIdx + 600;
      const bloco = bodyText.substring(startIdx, endIdx);

      const valorIdx = bloco.indexOf("R$ ");
      if (valorIdx === -1) continue;
      const valorStr = bloco.substring(valorIdx + 3, valorIdx + 25).match(/^[\d.,]+/);
      if (!valorStr) continue;
      const valor = parseValor(valorStr[0]);
      if (!valor || valor < 100) continue;

      const habilitado = !bloco.includes("Inabilitada") && !bloco.includes("Desclassificada");
      const lines = bloco.split("\n").map(l => l.trim()).filter(l => l.length > 5);
      let empresa = "";
      for (const line of lines) {
        if (line.match(/^\d{2}\.\d{3}/) || line.includes("R$") || line.includes("Valor") || line.includes("ME/EPP") || line.includes("Programa") || line.includes("Equidade") || line.includes("Inabilitada") || line.includes("Desclassificada") || line.includes("Aceita")) continue;
        if (line.match(/^[A-ZÀ-Ú0-9]/) && !line.match(/^[A-Z]{2}$/)) { empresa = line; break; }
      }
      if (!empresa) continue;

      const isNosso = empresa.toUpperCase().includes("MANUTEC") || empresa.toUpperCase().includes("MIAMI");
      if (isNosso) { nossaPosicao = pos; nossoLance = valor; }

      dados.classificacao.push({
        posicao: pos++, cnpj, empresa: empresa.substring(0, 100),
        valor_lance_final: valor, habilitado, status: bloco.includes("Inabilitada") ? "Inabilitada" : bloco.includes("Desclassificada") ? "Desclassificada" : "", nosso: isNosso,
      });
    }
  }

  // Define nossa posição e lance
  if (nossaPosicao) {
    dados.nossa_posicao = nossaPosicao;
    dados.nosso_lance = nossoLance;
  }

  // Extrai valor estimado/teto
  const tetoMatch = bodyText.match(/Valor estimado[^R]*R\$\s*([\d.,]+)/);
  if (tetoMatch) dados.valor_teto = parseValor(tetoMatch[1]);

  // CAPTURA CHAT: busca mensagens em accordions expandidos e seções de chat
  document.querySelectorAll('[class*="chat"], [class*="mensagem"], [class*="msg-"], [class*="timeline"], [class*="historico"]').forEach(el => {
    const text = el.innerText.trim();
    if (text.length > 5 && text.length < 3000 && !text.includes("Valor ofertado")) {
      const lines = text.split("\n").filter(l => l.trim().length > 3);
      lines.forEach(line => {
        const l = line.trim();
        if (l.length < 5 || l.length > 500) return;
        // Detecta remetente
        let remetente = "sistema";
        if (/pregoeiro|autoridade/i.test(l)) remetente = "pregoeiro";
        else if (/fornecedor|empresa/i.test(l)) remetente = "fornecedor";
        // Extrai horário
        const hora = l.match(/(\d{2}\/\d{2}\/\d{4}\s+\d{2}:\d{2}|\d{2}:\d{2}:\d{2}|\d{2}:\d{2})/);
        dados.mensagens.push({ remetente, mensagem: l.substring(0, 300), horario: hora ? hora[1] : "" });
      });
    }
  });

  // CAPTURA LANCES: busca tabelas/listas de lances dentro de accordions expandidos
  document.querySelectorAll('[class*="lance"], [class*="rodada"], [class*="negociacao"]').forEach(el => {
    const rows = el.querySelectorAll("tr, [class*='row']");
    rows.forEach(row => {
      const text = row.innerText;
      const valorMatch = text.match(/R\$\s*([\d.,]+)/);
      const cnpjMatch = text.match(/(\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2})/);
      const horaMatch = text.match(/(\d{2}:\d{2}(:\d{2})?)/);
      if (valorMatch) {
        dados.lances.push({
          empresa: cnpjMatch ? cnpjMatch[1] : "",
          valor: parseValor(valorMatch[1]),
          horario: horaMatch ? horaMatch[1] : "",
          nosso: /MANUTEC|MIAMI/i.test(text),
        });
      }
    });
  });

  // CAPTURA RECURSOS: aba "Histórico de recursos"
  document.querySelectorAll('[class*="recurso"], [class*="resource"]').forEach(el => {
    const text = el.innerText.trim();
    if (text.length > 10) {
      dados.eventos.push({ tipo: "recurso", descricao: text.substring(0, 500) });
    }
  });

  // STATUS da contratação
  const statusMatch = bodyText.match(/(?:Contratação na etapa de|Julgado e habilitado|Em fase de|Encerrada|Aberta para|Suspensa)[^.)\n]*/i);
  if (statusMatch) dados.status_pregao = statusMatch[0].trim();

  console.log(`[LicitacoesAI] ComprasGov: ${dados.classificacao.length} empresas, ${dados.mensagens.length} msgs, ${dados.lances.length} lances. Nossa posição: ${nossaPosicao || "—"}`);
  return dados;
}

// ══════════════════════════════════════════════
// EXTRATOR SIGA (Estado RJ)
// ══════════════════════════════════════════════

function extrairSIGA() {
  const dados = extrairPortalGenerico("siga");
  // SIGA RJ: tabelas HTML com fornecedores, lances e mensagens
  // URL: https://www.compras.rj.gov.br ou siga.fazenda.rj.gov.br
  const titulo = document.title || "";
  const pregaoMatch = titulo.match(/(\d+\/\d{4})/);
  if (pregaoMatch) dados.numero_pregao = pregaoMatch[1];
  return dados;
}

function extrairComprasRJ() {
  const dados = extrairPortalGenerico("comprasrj");
  // ComprasRJ: /EditaisLicitacoes/*, tabelas HTML
  const urlMatch = window.location.href.match(/id=(\d+)/);
  if (urlMatch) dados.compra_id = urlMatch[1];
  return dados;
}

function extrairLicitacoesE() {
  const dados = extrairPortalGenerico("licitacoes-e");
  // Licitações-e (BB): /aop/*, tabelas HTML + iframes
  const urlMatch = window.location.href.match(/(?:idLicitacao|licitacao)=(\d+)/i);
  if (urlMatch) dados.compra_id = urlMatch[1];
  // Tenta iframes
  document.querySelectorAll("iframe").forEach(iframe => {
    try {
      const doc = iframe.contentDocument;
      if (doc) extrairTabelasFornecedores(doc, dados);
    } catch (e) { /* cross-origin */ }
  });
  return dados;
}

function extrairBLL() {
  const dados = extrairPortalGenerico("bll");
  // BLL: /Process/*, React/Angular app
  const urlMatch = window.location.href.match(/Process\/(\d+)/i);
  if (urlMatch) dados.compra_id = urlMatch[1];
  return dados;
}

function extrairPortalCompras() {
  const dados = extrairPortalGenerico("portalcompras");
  // Portal Compras Públicas: tabelas HTML
  const urlMatch = window.location.href.match(/\/(\d+)(?:\?|$)/);
  if (urlMatch) dados.compra_id = urlMatch[1];
  return dados;
}

// ══════════════════════════════════════════════
// EXTRATOR GENÉRICO INTELIGENTE (funciona em qualquer portal)
// ══════════════════════════════════════════════

function extrairPortalGenerico(portalName) {
  const dados = {
    portal: portalName,
    tipo: detectarPagina(),
    url: window.location.href,
    timestamp: new Date().toISOString(),
    compra_id: null,
    title: document.title,
    titulo: document.body.innerText.substring(0, 1000),
    classificacao: [],
    lances: [],
    mensagens: [],
    propostas: [],
    eventos: [],
    nossa_empresa: "MANUTEC",
  };

  const bodyText = document.body.innerText;

  // Extrai UASG/órgão
  const uasgMatch = bodyText.match(/UASG\s*(\d+)/);
  if (uasgMatch) dados.uasg = uasgMatch[1];
  const orgaoMatch = bodyText.match(/(?:Órgão|Orgao|Entidade|Unidade)[:\s]+([^\n]{5,60})/i);
  if (orgaoMatch) dados.orgao_nome = orgaoMatch[1].trim();
  const pregaoMatch = bodyText.match(/(?:Pregão|Concorrência|Dispensa|Licitação)\s*(?:Eletrônic[oa])?\s*N[°º]?\s*(\d+[\/\-]\d{4})/i);
  if (pregaoMatch) dados.numero_pregao = pregaoMatch[1];
  const tetoMatch = bodyText.match(/Valor\s*(?:estimado|referência|total)[^R]*R\$\s*([\d.,]+)/i);
  if (tetoMatch) dados.valor_teto = parseValor(tetoMatch[1]);
  const objetoMatch = bodyText.match(/(?:Objeto|Descrição)[:\s]+([^\n]{10,200})/i);
  if (objetoMatch) dados.objeto = objetoMatch[1].trim();

  // 1. Tenta DOM: cards de fornecedores
  const cards = document.querySelectorAll('.cp-itens-card, .cp-item-expansivel, [class*="fornecedor"], [class*="proposta-item"], [class*="bidder"], [class*="participante"]');
  if (cards.length > 0) {
    extrairCardsDOM(cards, dados);
  }

  // 2. Tenta tabelas HTML
  if (dados.classificacao.length === 0) {
    extrairTabelasFornecedores(document, dados);
  }

  // 3. Fallback: parse por CNPJ no texto
  if (dados.classificacao.length === 0) {
    extrairPorCNPJTexto(bodyText, dados);
  }

  // Chat/mensagens genérico
  document.querySelectorAll('[class*="chat"], [class*="mensagem"], [class*="msg"], [class*="aviso"], [class*="comunicado"]').forEach(el => {
    const text = el.innerText.trim();
    if (text.length > 5 && text.length < 2000) {
      dados.mensagens.push({ remetente: "sistema", mensagem: text.substring(0, 300), horario: extrairHorario(text) || "" });
    }
  });

  // Detecta nossa posição
  let nossaPosicao = null, nossoLance = null;
  dados.classificacao.forEach(c => {
    if (c.nosso) { nossaPosicao = c.posicao; nossoLance = c.valor_lance_final; }
  });
  if (nossaPosicao) { dados.nossa_posicao = nossaPosicao; dados.nosso_lance = nossoLance; }

  console.log(`[LicitacoesAI] ${portalName}: ${dados.classificacao.length} empresas, ${dados.mensagens.length} msgs, ${dados.lances.length} lances`);
  return dados;
}

// Extrai dados de cards DOM (ComprasGov e similares)
function extrairCardsDOM(cards, dados) {
  let pos = 1;
  cards.forEach(card => {
    const text = card.innerText;
    const cnpjMatch = text.match(/(\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2})/);
    if (!cnpjMatch) return;
    const valorMatch = text.match(/R\$\s*([\d.,]+)/);
    if (!valorMatch) return;
    const valor = parseValor(valorMatch[1]);
    if (!valor || valor < 100) return;

    const habilitado = !text.includes("Inabilitada") && !text.includes("Desclassificada");
    const statusText = text.includes("Inabilitada") ? "Inabilitada" : text.includes("Desclassificada") ? "Desclassificada" : text.includes("Aceita") ? "Aceita e habilitada" : "";

    const lines = text.split("\n").map(l => l.trim()).filter(l => l.length > 3);
    let empresa = "";
    for (const line of lines) {
      if (line.match(/^\d{2}\.\d{3}/) || line.includes("R$") || line.includes("Valor") || line.includes("ME/EPP") || line.includes("Programa") || line.includes("Equidade") || line.includes("Inabilitada") || line.includes("Desclassificada") || line.includes("Aceita") || line.length <= 3) continue;
      if (line.match(/^[A-ZÀ-Ú0-9]/) && !line.match(/^[A-Z]{2}$/)) { empresa = line; break; }
    }
    if (!empresa) return;

    const isNosso = /MANUTEC|MIAMI/i.test(empresa);
    dados.classificacao.push({ posicao: pos++, cnpj: cnpjMatch[1], empresa: empresa.substring(0, 100), valor_lance_final: valor, habilitado, status: statusText, nosso: isNosso });
  });
}

// Extrai dados de tabelas HTML (funciona em qualquer portal com tabelas)
function extrairTabelasFornecedores(doc, dados) {
  let pos = dados.classificacao.length + 1;
  doc.querySelectorAll("table").forEach(table => {
    const headers = Array.from(table.querySelectorAll("th")).map(th => th.textContent.trim().toLowerCase());
    const hasEmpresa = headers.some(h => h.includes("fornecedor") || h.includes("empresa") || h.includes("razão") || h.includes("licitante") || h.includes("participante"));
    const hasValor = headers.some(h => h.includes("valor") || h.includes("preço") || h.includes("lance") || h.includes("proposta"));

    if (hasEmpresa || hasValor) {
      const rows = Array.from(table.querySelectorAll("tbody tr, tr")).slice(1);
      rows.forEach(row => {
        const cells = Array.from(row.querySelectorAll("td")).map(td => td.textContent.trim());
        if (cells.length < 2) return;
        const text = cells.join(" ");
        const cnpj = extrairCNPJ(text);
        const valorMatch = text.match(/R?\$?\s*([\d.,]{5,})/);
        const valor = valorMatch ? parseValor(valorMatch[1]) : null;
        if (!valor || valor < 100) return;

        let empresa = "";
        for (const cell of cells) {
          if (cell.length > 5 && cell.match(/^[A-ZÀ-Ú]/) && !cell.match(/^\d/) && !cell.includes("R$")) {
            empresa = cell; break;
          }
        }
        if (!empresa) return;

        const hab = !text.toLowerCase().includes("inabil") && !text.toLowerCase().includes("desclass");
        const isNosso = /MANUTEC|MIAMI/i.test(empresa);
        dados.classificacao.push({ posicao: pos++, cnpj, empresa: empresa.substring(0, 100), valor_lance_final: valor, habilitado: hab, nosso: isNosso });
      });
    }
  });
}

// Fallback: parse CNPJ no texto livre
function extrairPorCNPJTexto(bodyText, dados) {
  const cnpjPattern = /\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}/g;
  const cnpjs = [];
  let m;
  while ((m = cnpjPattern.exec(bodyText)) !== null) cnpjs.push({ cnpj: m[0], index: m.index });

  let pos = dados.classificacao.length + 1;
  for (let i = 0; i < cnpjs.length; i++) {
    const { cnpj, index: startIdx } = cnpjs[i];
    const endIdx = i + 1 < cnpjs.length ? cnpjs[i + 1].index : startIdx + 600;
    const bloco = bodyText.substring(startIdx, endIdx);

    const valorIdx = bloco.indexOf("R$ ");
    if (valorIdx === -1) continue;
    const valorStr = bloco.substring(valorIdx + 3, valorIdx + 25).match(/^[\d.,]+/);
    if (!valorStr) continue;
    const valor = parseValor(valorStr[0]);
    if (!valor || valor < 100) continue;

    const hab = !bloco.includes("Inabilitada") && !bloco.includes("Desclassificada");
    const lines = bloco.split("\n").map(l => l.trim()).filter(l => l.length > 5);
    let empresa = "";
    for (const line of lines) {
      if (line.match(/^\d{2}\.\d{3}/) || line.includes("R$") || line.includes("Valor") || line.includes("ME/EPP") || line.includes("Programa")) continue;
      if (line.match(/^[A-ZÀ-Ú0-9]/) && !line.match(/^[A-Z]{2}$/)) { empresa = line; break; }
    }
    if (!empresa) continue;

    const isNosso = /MANUTEC|MIAMI/i.test(empresa);
    dados.classificacao.push({ posicao: pos++, cnpj, empresa: empresa.substring(0, 100), valor_lance_final: valor, habilitado: hab, nosso: isNosso });
  }
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
    default: return extrairPortalGenerico("desconhecido");
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
