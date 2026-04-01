const DASHBOARD_URL = "https://pncp-bot-production.up.railway.app";

// ══════════════════════════════════════════════
// TABS
// ══════════════════════════════════════════════

function showTab(tab) {
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".tab").forEach(t => { t.classList.remove("active"); t.classList.add("inactive"); });
  document.getElementById(`panel-${tab}`).classList.add("active");
  document.getElementById(`tab-${tab}`).classList.add("active");
  document.getElementById(`tab-${tab}`).classList.remove("inactive");
}

// ══════════════════════════════════════════════
// CAPTURA (tab existente melhorada)
// ══════════════════════════════════════════════

async function checkDashboard() {
  const el = document.getElementById("dashboard");
  try {
    const resp = await fetch(`${DASHBOARD_URL}/api/health`, { signal: AbortSignal.timeout(5000) });
    const data = await resp.json();
    el.textContent = data.status === "ok" ? "Online" : "Erro";
    el.className = "value " + (data.status === "ok" ? "green" : "red");
  } catch {
    el.textContent = "Offline";
    el.className = "value red";
  }
}

function checkStatus() {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (!tabs[0]) return;
    chrome.tabs.sendMessage(tabs[0].id, { type: "get_status" }, (response) => {
      if (response) {
        document.getElementById("portal").textContent = response.portal || "—";
        document.getElementById("pagina").textContent = response.pagina || "—";
      }
    });
    // Verifica formulário de lance
    chrome.tabs.sendMessage(tabs[0].id, { type: "robot_detectar_form" }, (response) => {
      const el = document.getElementById("form-lance");
      if (response?.found) {
        el.textContent = "Detectado ✓";
        el.className = "value green";
      } else {
        el.textContent = "Não encontrado";
        el.className = "value red";
      }
    });
    // Status do robô
    chrome.tabs.sendMessage(tabs[0].id, { type: "robot_get_status" }, (response) => {
      if (response) {
        updateRobotUI(response);
      }
    });
  });
}

function updateCaptura() {
  chrome.storage.local.get(["lastCapture"], (data) => {
    if (!data.lastCapture) return;
    const cap = data.lastCapture;
    const total = (cap.classificacao?.length || 0) + (cap.lances?.length || 0) + (cap.mensagens?.length || 0);
    document.getElementById("contagem").textContent = `${cap.classificacao?.length || 0} empresas`;
    document.getElementById("ultima").textContent = cap.timestamp ? new Date(cap.timestamp).toLocaleTimeString() : "—";

    const container = document.getElementById("dados");
    if (cap.classificacao && cap.classificacao.length > 0) {
      container.innerHTML = cap.classificacao.slice(0, 15).map((c, i) => {
        const isNosso = c.nosso ? ' nosso' : '';
        const habClass = c.habilitado ? '' : ' inab';
        return `<div class="dados-item${isNosso}">
          <span class="${habClass}">${c.posicao}. ${(c.empresa || "").substring(0, 30)}${c.nosso ? " ⭐" : ""}</span>
          <span class="valor">R$ ${(c.valor_lance_final || 0).toLocaleString("pt-BR")}${!c.habilitado ? " ✕" : ""}</span>
        </div>`;
      }).join("");
    }
  });
}

// ══════════════════════════════════════════════
// ROBÔ
// ══════════════════════════════════════════════

function updateRobotUI(status) {
  const badge = document.getElementById("robot-badge");
  const statusEl = document.getElementById("robot-status");
  const iniciarBtn = document.getElementById("iniciar-robot");
  const pararBtn = document.getElementById("parar-robot");

  if (status.ativo) {
    badge.style.display = "inline";
    badge.textContent = "ROBOT ON";
    badge.style.background = "#BEFF3A";
    badge.style.color = "#09090B";
    statusEl.textContent = "Ativo ⚡";
    statusEl.className = "value green";
    iniciarBtn.style.display = "none";
    pararBtn.style.display = "block";
    if (status.config) {
      document.getElementById("robot-modo").textContent = status.config.modo === "auto" ? "Automático" : "Semi-automático";
      document.getElementById("robot-estrategia").textContent = status.config.estrategia;
    }
  } else {
    badge.style.display = "inline";
    badge.textContent = "ROBOT OFF";
    badge.style.background = "#FF4D4D";
    badge.style.color = "#FFF";
    statusEl.textContent = "Desativado";
    statusEl.className = "value red";
    iniciarBtn.style.display = "block";
    pararBtn.style.display = "none";
  }
}

function checkSugestao() {
  chrome.storage.local.get(["lastSugestao"], (data) => {
    const container = document.getElementById("sugestao-container");
    if (!data.lastSugestao) {
      container.style.display = "none";
      return;
    }
    const s = data.lastSugestao;
    if (s.acao === "confirmar" || s.acao === "enviar") {
      container.style.display = "block";
      document.getElementById("lance-sugerido").textContent = `R$ ${s.lance_sugerido?.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;
      document.getElementById("estrategia-usada").textContent = s.estrategia;
      document.getElementById("desconto-sugerido").textContent = `${s.desconto_pct?.toFixed(1)}%`;
      document.getElementById("motivo-lance").textContent = s.motivo;
    } else {
      container.style.display = "none";
    }
  });
}

// ══════════════════════════════════════════════
// EVENT LISTENERS
// ══════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
  // Tab navigation
  document.querySelectorAll("[data-tab]").forEach(btn => {
    btn.addEventListener("click", () => showTab(btn.dataset.tab));
  });

  checkDashboard();
  checkStatus();
  updateCaptura();
  checkSugestao();

  // Capturar
  document.getElementById("capturar").addEventListener("click", () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0]) return;
      chrome.tabs.sendMessage(tabs[0].id, { type: "capturar_agora" }, (response) => {
        if (response?.ok) {
          document.getElementById("contagem").textContent = `${response.dados?.classificacao?.length || 0} empresas`;
          setTimeout(updateCaptura, 1000);
        }
      });
    });
  });

  // Abrir dashboard
  document.getElementById("abrir").addEventListener("click", () => {
    chrome.tabs.create({ url: DASHBOARD_URL });
  });

  // Iniciar robô
  document.getElementById("iniciar-robot").addEventListener("click", () => {
    const config = {
      modo: document.getElementById("cfg-modo").value,
      estrategia: document.getElementById("cfg-estrategia").value,
      valor_minimo: parseFloat(document.getElementById("cfg-valor-min").value) || 0,
      desconto_maximo_pct: parseFloat(document.getElementById("cfg-desconto-max").value) || 25,
      intervalo_lances_seg: parseInt(document.getElementById("cfg-intervalo").value) || 10,
      empresa: document.getElementById("cfg-empresa").value,
    };

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0]) return;
      // Salva config no servidor primeiro
      chrome.runtime.sendMessage({ type: "robot_configurar", pregao_id: 1, config }, (resp) => {
        // Inicia robô na página
        chrome.tabs.sendMessage(tabs[0].id, { type: "robot_iniciar", pregao_id: 1, config }, (response) => {
          if (response?.ok) {
            updateRobotUI({ ativo: true, config });
          }
        });
      });
    });
  });

  // Parar robô
  document.getElementById("parar-robot").addEventListener("click", () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0]) return;
      chrome.tabs.sendMessage(tabs[0].id, { type: "robot_parar" }, () => {
        updateRobotUI({ ativo: false });
      });
    });
  });

  // Confirmar lance sugerido
  document.getElementById("confirmar-lance").addEventListener("click", () => {
    chrome.storage.local.get(["lastSugestao"], (data) => {
      if (!data.lastSugestao) return;
      const valor = data.lastSugestao.lance_sugerido;
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (!tabs[0]) return;
        chrome.tabs.sendMessage(tabs[0].id, { type: "robot_lance_manual", valor }, (response) => {
          if (response?.ok) {
            document.getElementById("sugestao-container").style.display = "none";
            chrome.storage.local.remove("lastSugestao");
          }
        });
      });
    });
  });

  // Rejeitar lance
  document.getElementById("rejeitar-lance").addEventListener("click", () => {
    document.getElementById("sugestao-container").style.display = "none";
    chrome.storage.local.remove("lastSugestao");
  });

  // Lance manual
  document.getElementById("lance-manual-btn").addEventListener("click", () => {
    const input = document.getElementById("lance-manual-valor");
    const valor = parseFloat(input.value.replace(/[R$\s.]/g, "").replace(",", "."));
    if (!valor || valor < 100) { alert("Valor inválido"); return; }
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0]) return;
      chrome.tabs.sendMessage(tabs[0].id, { type: "robot_lance_manual", valor }, (response) => {
        if (response?.ok) {
          input.value = "";
          alert("Lance enviado!");
        } else {
          alert("Erro: " + (response?.error || "desconhecido"));
        }
      });
    });
  });

  // Salvar config
  document.getElementById("salvar-config").addEventListener("click", () => {
    const config = {
      modo: document.getElementById("cfg-modo").value,
      estrategia: document.getElementById("cfg-estrategia").value,
      valor_minimo: parseFloat(document.getElementById("cfg-valor-min").value) || 0,
      desconto_maximo_pct: parseFloat(document.getElementById("cfg-desconto-max").value) || 25,
      intervalo_lances_seg: parseInt(document.getElementById("cfg-intervalo").value) || 10,
      empresa: document.getElementById("cfg-empresa").value,
      notificar_telegram: true,
    };
    chrome.storage.local.set({ robotConfig: config });
    chrome.runtime.sendMessage({ type: "robot_configurar", pregao_id: 1, config }, (resp) => {
      alert(resp?.ok ? "Configuração salva!" : "Erro ao salvar");
    });
  });

  // Carregar config
  document.getElementById("carregar-config").addEventListener("click", () => {
    chrome.storage.local.get(["robotConfig"], (data) => {
      if (data.robotConfig) {
        const c = data.robotConfig;
        document.getElementById("cfg-modo").value = c.modo || "semi_auto";
        document.getElementById("cfg-estrategia").value = c.estrategia || "conservador";
        document.getElementById("cfg-valor-min").value = c.valor_minimo || "";
        document.getElementById("cfg-desconto-max").value = c.desconto_maximo_pct || 25;
        document.getElementById("cfg-intervalo").value = c.intervalo_lances_seg || 10;
        document.getElementById("cfg-empresa").value = c.empresa || "MANUTEC";
      }
    });
  });

  // Auto-refresh a cada 5s
  setInterval(() => {
    updateCaptura();
    checkSugestao();
    checkStatus();
  }, 5000);
});
