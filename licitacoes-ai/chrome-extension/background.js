/**
 * Background Service Worker — gerencia estado da extensão
 */

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "sync_ok") {
    // Atualiza badge
    chrome.action.setBadgeText({ text: "OK" });
    chrome.action.setBadgeBackgroundColor({ color: "#22C55E" });
    setTimeout(() => chrome.action.setBadgeText({ text: "" }), 3000);
  }
});

// Badge inicial
chrome.action.setBadgeText({ text: "" });
