const DASHBOARD_URL = "https://pncp-bot-production.up.railway.app";

// Verifica status do dashboard
async function checkDashboard() {
  const el = document.getElementById("dashboard");
  try {
    const resp = await fetch(`${DASHBOARD_URL}/api/health`, { signal: AbortSignal.timeout(3000) });
    if (resp.ok) {
      el.textContent = "Online";
      el.className = "status-value online";
    } else {
      el.textContent = "Erro";
      el.className = "status-value offline";
    }
  } catch {
    el.textContent = "Offline";
    el.className = "status-value offline";
  }
}

// Pede status ao content script
function updateStatus() {
  chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
    if (!tabs[0]) return;
    chrome.tabs.sendMessage(tabs[0].id, { type: "get_status" }, response => {
      if (response) {
        document.getElementById("pagina").textContent =
          response.pagina === "acompanhamento" ? "Acompanhamento" :
          response.pagina === "lista" ? "Lista de Compras" : "Outra";
      } else {
        document.getElementById("pagina").textContent = "Fora do ComprasGov";
      }
    });
  });
}

// Carrega última captura
function loadLastCapture() {
  chrome.storage.local.get("lastCapture", result => {
    const dados = result.lastCapture;
    if (!dados) return;

    document.getElementById("ultima").textContent = new Date(dados.timestamp).toLocaleTimeString("pt-BR");

    const total = (dados.classificacao?.length || 0) + (dados.lances?.length || 0) + (dados.mensagens?.length || 0);
    document.getElementById("contagem").textContent = `${total} itens`;

    const container = document.getElementById("dados");

    if (dados.classificacao?.length > 0) {
      container.innerHTML = "<strong style='color:#98968E;font-size:10px'>CLASSIFICACAO</strong>";
      dados.classificacao.forEach(c => {
        container.innerHTML += `
          <div class="dados-item">
            <span>${c.posicao}.</span>
            <span class="empresa">${c.empresa || "—"}</span>
            <span class="valor">${c.valor_lance_final ? "R$ " + c.valor_lance_final.toLocaleString("pt-BR") : "—"}</span>
          </div>`;
      });
    } else if (dados.lances?.length > 0) {
      container.innerHTML = "<strong style='color:#98968E;font-size:10px'>LANCES</strong>";
      dados.lances.slice(-10).forEach(l => {
        container.innerHTML += `
          <div class="dados-item">
            <span class="empresa">${l.empresa || "—"}</span>
            <span class="valor">${l.valor ? "R$ " + l.valor.toLocaleString("pt-BR") : "—"}</span>
          </div>`;
      });
    } else if (dados.mensagens?.length > 0) {
      container.innerHTML = "<strong style='color:#98968E;font-size:10px'>MENSAGENS</strong>";
      dados.mensagens.slice(-5).forEach(m => {
        container.innerHTML += `
          <div class="dados-item">
            <strong style="color:#5A9EF7">${m.remetente}</strong>: ${m.mensagem?.substring(0, 80) || "—"}
          </div>`;
      });
    }
  });
}

// Botão capturar
document.getElementById("capturar").addEventListener("click", () => {
  chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
    if (!tabs[0]) return;
    chrome.tabs.sendMessage(tabs[0].id, { type: "capturar_agora" }, response => {
      if (response?.ok) {
        document.getElementById("capturar").textContent = "Capturado!";
        setTimeout(() => {
          document.getElementById("capturar").textContent = "Capturar Agora";
          loadLastCapture();
        }, 2000);
      }
    });
  });
});

// Botão abrir dashboard
document.getElementById("abrir").addEventListener("click", () => {
  chrome.tabs.create({ url: DASHBOARD_URL });
});

// Init
checkDashboard();
updateStatus();
loadLastCapture();
