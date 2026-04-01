/**
 * Robô de Disputa — Lances Automáticos Multi-Portal
 * Monitora sessão, calcula lance ideal, preenche e envia
 */

const ROBOT_API = "https://pncp-bot-production.up.railway.app/api/pregoes";
let robotAtivo = false;
let robotInterval = null;
let robotConfig = null;
let ultimoLanceLider = null;

// ══════════════════════════════════════════════
// DETECÇÃO DE FORMULÁRIO DE LANCE
// ══════════════════════════════════════════════

function detectarFormularioLance() {
  const portal = detectarPortal();
  let input = null;
  let button = null;
  let found = false;

  // ComprasGov
  if (portal === "comprasgov") {
    input = document.querySelector('input[name*="valor"], input[name*="lance"], input[placeholder*="lance"], input[placeholder*="valor"], input.valor-lance, input[formcontrolname*="valor"]');
    button = document.querySelector('button[class*="lance"], button[class*="enviar"], button[type="submit"]');
    // Tenta seletores Angular/PrimeNG
    if (!input) input = document.querySelector('.p-inputnumber input, p-inputnumber input, [id*="lance"] input');
    if (!button) {
      document.querySelectorAll("button").forEach(b => {
        const text = b.textContent.toLowerCase();
        if (text.includes("fazer lance") || text.includes("enviar lance") || text.includes("dar lance") || text.includes("registrar lance")) {
          button = b;
        }
      });
    }
  }

  // SIGA RJ
  if (portal === "siga") {
    input = document.querySelector('input[name="valor"], input[name="valorLance"], #valorLance, #valor');
    button = document.querySelector('input[type="submit"][value*="Lance"], button[type="submit"]');
  }

  // ComprasRJ
  if (portal === "comprasrj") {
    input = document.querySelector('input[name*="valor"], input[id*="valor"]');
    button = document.querySelector('button[type="submit"], input[type="submit"]');
  }

  // Licitações-e (BB)
  if (portal === "licitacoes-e") {
    // Tenta dentro de iframes
    document.querySelectorAll("iframe").forEach(iframe => {
      try {
        const doc = iframe.contentDocument;
        if (doc) {
          input = input || doc.querySelector('input[name*="valor"], input[name*="lance"]');
          button = button || doc.querySelector('input[type="submit"], button[type="submit"]');
        }
      } catch (e) { /* cross-origin */ }
    });
    if (!input) input = document.querySelector('input[name*="valor"]');
    if (!button) button = document.querySelector('button[type="submit"]');
  }

  // BLL
  if (portal === "bll") {
    input = document.querySelector('input[name*="valor"], input[placeholder*="valor"], [class*="bid-input"] input');
    button = document.querySelector('button[class*="bid"], button[class*="lance"]');
  }

  // Portal Compras Públicas
  if (portal === "portalcompras") {
    input = document.querySelector('input[name*="valor"], input[id*="valor"]');
    button = document.querySelector('button[type="submit"], [class*="enviar"]');
  }

  // Fallback genérico
  if (!input) {
    document.querySelectorAll("input").forEach(el => {
      const ph = (el.placeholder || "").toLowerCase();
      const nm = (el.name || "").toLowerCase();
      if ((ph.includes("lance") || ph.includes("valor") || nm.includes("lance") || nm.includes("valor")) && el.type !== "hidden") {
        input = el;
      }
    });
  }

  found = !!(input && button);
  return { input, button, found, portal };
}

// ══════════════════════════════════════════════
// PREENCHER E ENVIAR LANCE
// ══════════════════════════════════════════════

async function enviarLance(valor, confirmar = true) {
  const form = detectarFormularioLance();
  if (!form.found) {
    console.warn("[ROBOT] Formulário de lance não encontrado");
    return { ok: false, error: "Formulário de lance não encontrado na página" };
  }

  // Confirmação
  if (confirmar) {
    const ok = confirm(`🤖 ROBÔ DE DISPUTA\n\nEnviar lance: R$ ${valor.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}\n\nConfirmar?`);
    if (!ok) return { ok: false, error: "Cancelado pelo usuário" };
  }

  try {
    // Preenche input
    const inputEl = form.input;
    const valorStr = valor.toFixed(2).replace(".", ",");

    // Limpa e preenche (compatível com Angular/React)
    inputEl.focus();
    inputEl.value = "";
    const nativeSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    nativeSetter.call(inputEl, valorStr);
    inputEl.dispatchEvent(new Event("input", { bubbles: true }));
    inputEl.dispatchEvent(new Event("change", { bubbles: true }));
    inputEl.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true }));

    // Aguarda processamento do framework
    await new Promise(r => setTimeout(r, 500));

    // Clica no botão
    form.button.click();

    // Aguarda possível modal de confirmação
    await new Promise(r => setTimeout(r, 1000));

    // Tenta clicar em botão de confirmação do modal
    document.querySelectorAll("button").forEach(b => {
      const text = b.textContent.toLowerCase();
      if (text.includes("sim") || text.includes("confirmar") || text.includes("ok") || text.includes("enviar")) {
        if (b.offsetParent !== null) { // visível
          b.click();
        }
      }
    });

    console.log(`[ROBOT] Lance R$ ${valorStr} enviado com sucesso!`);
    return { ok: true, valor, portal: form.portal };

  } catch (e) {
    console.error("[ROBOT] Erro ao enviar lance:", e);
    return { ok: false, error: e.message };
  }
}

// ══════════════════════════════════════════════
// MONITOR DE SESSÃO ATIVA
// ══════════════════════════════════════════════

function iniciarRobot(pregaoId, config) {
  if (robotAtivo) pararRobot();

  robotConfig = config;
  robotAtivo = true;
  ultimoLanceLider = null;

  const intervalo = (config.intervalo_lances_seg || 5) * 1000;

  console.log(`[ROBOT] Iniciado! Pregão ${pregaoId} | Modo: ${config.modo} | Estratégia: ${config.estrategia} | Intervalo: ${intervalo / 1000}s`);

  robotInterval = setInterval(async () => {
    if (!robotAtivo) return;

    // Extrai dados atuais da página
    const dados = extrairDados();
    if (!dados || dados.classificacao.length === 0) return;

    // Acha líder atual e nossa posição
    const sorted = [...dados.classificacao].sort((a, b) => (a.valor_lance_final || Infinity) - (b.valor_lance_final || Infinity));
    const lider = sorted[0];
    const nosso = sorted.find(c => c.nosso);

    if (!lider) return;

    // Verifica se houve mudança
    if (lider.valor_lance_final === ultimoLanceLider) return;
    ultimoLanceLider = lider.valor_lance_final;

    // Se já somos o líder, não faz nada
    if (nosso && nosso.posicao === 1) {
      console.log("[ROBOT] Somos o líder. Mantendo posição.");
      return;
    }

    // Chama API para calcular próximo lance
    try {
      const resp = await new Promise((resolve) => {
        chrome.runtime.sendMessage({
          type: "robot_calcular",
          pregao_id: pregaoId,
          data: {
            valor_atual_lider: lider.valor_lance_final,
            nossa_posicao: nosso?.posicao || 0,
            nosso_lance_atual: nosso?.valor_lance_final || 0,
            total_participantes: dados.classificacao.length,
            rodada: dados.lances?.length || 1,
          },
        }, resolve);
      });

      if (!resp?.ok) return;
      const calc = resp.result;

      console.log(`[ROBOT] ${calc.acao}: R$ ${calc.lance_sugerido?.toLocaleString("pt-BR")} (${calc.motivo})`);

      // Notifica extensão
      chrome.runtime.sendMessage({
        type: "robot_sugestao",
        data: calc,
      });

      // Ação
      if (calc.acao === "enviar") {
        // Modo auto: envia direto
        const result = await enviarLance(calc.lance_sugerido, false);
        // Registra
        chrome.runtime.sendMessage({
          type: "robot_registrar",
          pregao_id: pregaoId,
          data: {
            valor: calc.lance_sugerido,
            valor_anterior: nosso?.valor_lance_final || 0,
            posicao_antes: nosso?.posicao || 0,
            estrategia_usada: calc.estrategia,
            modo: "auto",
            portal: detectarPortal(),
            sucesso: result.ok,
            erro: result.error || null,
          },
        });
      } else if (calc.acao === "confirmar") {
        // Modo semi-auto: mostra popup de confirmação
        const result = await enviarLance(calc.lance_sugerido, true);
        if (result.ok) {
          chrome.runtime.sendMessage({
            type: "robot_registrar",
            pregao_id: pregaoId,
            data: {
              valor: calc.lance_sugerido,
              valor_anterior: nosso?.valor_lance_final || 0,
              posicao_antes: nosso?.posicao || 0,
              estrategia_usada: calc.estrategia,
              modo: "semi_auto",
              portal: detectarPortal(),
              sucesso: true,
            },
          });
        }
      }
      // "manter" e "bloquear" não fazem nada

    } catch (e) {
      console.error("[ROBOT] Erro no ciclo:", e);
    }
  }, intervalo);

  // Badge
  chrome.runtime.sendMessage({ type: "robot_status", ativo: true });
}

function pararRobot() {
  robotAtivo = false;
  if (robotInterval) clearInterval(robotInterval);
  robotInterval = null;
  robotConfig = null;
  console.log("[ROBOT] Parado.");
  chrome.runtime.sendMessage({ type: "robot_status", ativo: false });
}

// ══════════════════════════════════════════════
// MENSAGENS DO POPUP/BACKGROUND
// ══════════════════════════════════════════════

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "robot_iniciar") {
    iniciarRobot(msg.pregao_id, msg.config);
    sendResponse({ ok: true });
  }
  if (msg.type === "robot_parar") {
    pararRobot();
    sendResponse({ ok: true });
  }
  if (msg.type === "robot_lance_manual") {
    enviarLance(msg.valor, true).then(r => sendResponse(r));
    return true;
  }
  if (msg.type === "robot_detectar_form") {
    const form = detectarFormularioLance();
    sendResponse({ found: form.found, portal: form.portal });
  }
  if (msg.type === "robot_get_status") {
    sendResponse({ ativo: robotAtivo, config: robotConfig });
  }
});
