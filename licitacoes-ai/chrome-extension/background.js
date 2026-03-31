/**
 * Background Service Worker — proxy para API (evita CORS)
 */

const DASHBOARD_API = "https://pncp-bot-production.up.railway.app/api";

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "sync_ok") {
    chrome.action.setBadgeText({ text: "OK" });
    chrome.action.setBadgeBackgroundColor({ color: "#22C55E" });
    setTimeout(() => chrome.action.setBadgeText({ text: "" }), 3000);
  }

  // Proxy: content script envia dados via background (sem CORS)
  if (msg.type === "enviar_dados") {
    fetch(`${DASHBOARD_API}/pregoes/extension/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(msg.data),
    })
      .then(resp => resp.json())
      .then(result => {
        console.log("[LicitacoesAI BG] Sync OK:", result);
        chrome.action.setBadgeText({ text: `${result.saved?.classificacao || 0}` });
        chrome.action.setBadgeBackgroundColor({ color: "#22C55E" });
        setTimeout(() => chrome.action.setBadgeText({ text: "" }), 5000);
        sendResponse({ ok: true, result });
      })
      .catch(err => {
        console.error("[LicitacoesAI BG] Sync ERRO:", err.message);
        chrome.action.setBadgeText({ text: "!" });
        chrome.action.setBadgeBackgroundColor({ color: "#FF4D4D" });
        sendResponse({ ok: false, error: err.message });
      });
    return true; // async sendResponse
  }
});

chrome.action.setBadgeText({ text: "" });
