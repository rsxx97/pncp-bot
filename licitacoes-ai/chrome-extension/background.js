/**
 * Background Service Worker — proxy API + gerenciador do robô de disputa
 */

const DASHBOARD_API = "https://pncp-bot-production.up.railway.app/api";

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  // Sync de dados (extensão → dashboard)
  if (msg.type === "sync_ok") {
    chrome.action.setBadgeText({ text: "OK" });
    chrome.action.setBadgeBackgroundColor({ color: "#22C55E" });
    setTimeout(() => chrome.action.setBadgeText({ text: "" }), 3000);
  }

  // Proxy: enviar dados capturados
  if (msg.type === "enviar_dados") {
    fetch(`${DASHBOARD_API}/pregoes/extension/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(msg.data),
    })
      .then(resp => resp.json())
      .then(result => {
        chrome.action.setBadgeText({ text: `${result.saved?.classificacao || 0}` });
        chrome.action.setBadgeBackgroundColor({ color: "#22C55E" });
        setTimeout(() => chrome.action.setBadgeText({ text: "" }), 5000);
        sendResponse({ ok: true, result });
      })
      .catch(err => {
        chrome.action.setBadgeText({ text: "!" });
        chrome.action.setBadgeBackgroundColor({ color: "#FF4D4D" });
        sendResponse({ ok: false, error: err.message });
      });
    return true;
  }

  // ═══ ROBÔ DE DISPUTA ═══

  // Calcular próximo lance
  if (msg.type === "robot_calcular") {
    fetch(`${DASHBOARD_API}/pregoes/${msg.pregao_id}/robot/calcular`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(msg.data),
    })
      .then(resp => resp.json())
      .then(result => sendResponse({ ok: true, result }))
      .catch(err => sendResponse({ ok: false, error: err.message }));
    return true;
  }

  // Registrar lance enviado
  if (msg.type === "robot_registrar") {
    fetch(`${DASHBOARD_API}/pregoes/${msg.pregao_id}/robot/registrar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(msg.data),
    })
      .then(resp => resp.json())
      .then(result => {
        chrome.action.setBadgeText({ text: "✓" });
        chrome.action.setBadgeBackgroundColor({ color: "#BEFF3A" });
        setTimeout(() => chrome.action.setBadgeText({ text: "" }), 3000);
        sendResponse({ ok: true, result });
      })
      .catch(err => sendResponse({ ok: false, error: err.message }));
    return true;
  }

  // Status do robô (badge)
  if (msg.type === "robot_status") {
    if (msg.ativo) {
      chrome.action.setBadgeText({ text: "🤖" });
      chrome.action.setBadgeBackgroundColor({ color: "#BEFF3A" });
    } else {
      chrome.action.setBadgeText({ text: "" });
    }
  }

  // Sugestão de lance (notifica popup)
  if (msg.type === "robot_sugestao") {
    chrome.storage.local.set({ lastSugestao: msg.data });
  }

  // Configurar robô
  if (msg.type === "robot_configurar") {
    fetch(`${DASHBOARD_API}/pregoes/${msg.pregao_id}/robot/configurar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(msg.config),
    })
      .then(resp => resp.json())
      .then(result => sendResponse({ ok: true, result }))
      .catch(err => sendResponse({ ok: false, error: err.message }));
    return true;
  }

  // Status do robô no servidor
  if (msg.type === "robot_get_server_status") {
    fetch(`${DASHBOARD_API}/pregoes/${msg.pregao_id}/robot/status`)
      .then(resp => resp.json())
      .then(result => sendResponse({ ok: true, result }))
      .catch(err => sendResponse({ ok: false, error: err.message }));
    return true;
  }
});

chrome.action.setBadgeText({ text: "" });
