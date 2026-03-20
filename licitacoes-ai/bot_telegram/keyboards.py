"""Teclados inline para o bot Telegram."""


def teclado_principal() -> dict:
    """Menu principal do bot."""
    return {
        "inline_keyboard": [
            [
                {"text": "📋 Oportunidades", "callback_data": "menu_oportunidades"},
                {"text": "📊 Relatórios", "callback_data": "menu_relatorios"},
            ],
            [
                {"text": "🔍 Buscar", "callback_data": "menu_buscar"},
                {"text": "⚙️ Config", "callback_data": "menu_config"},
            ],
            [
                {"text": "🔄 Executar Monitor", "callback_data": "executar_monitor"},
            ],
        ]
    }


def teclado_oportunidades() -> dict:
    """Submenu de oportunidades."""
    return {
        "inline_keyboard": [
            [
                {"text": "🆕 Novos", "callback_data": "oport_novos"},
                {"text": "✅ Go", "callback_data": "oport_go"},
            ],
            [
                {"text": "💰 Precificados", "callback_data": "oport_precificados"},
                {"text": "🎯 Prontos", "callback_data": "oport_prontos"},
            ],
            [
                {"text": "⭐ Favoritos", "callback_data": "oport_favoritos"},
                {"text": "❌ No-Go", "callback_data": "oport_nogo"},
            ],
            [
                {"text": "⬅️ Voltar", "callback_data": "menu_principal"},
            ],
        ]
    }


def teclado_edital(pncp_id: str, status: str = "novo") -> dict:
    """Ações para um edital específico."""
    botoes = []

    if status in ("novo", "classificado"):
        botoes.append([
            {"text": "🔍 Analisar", "callback_data": f"analisar_{pncp_id}"},
            {"text": "❌ Descartar", "callback_data": f"descartar_{pncp_id}"},
        ])

    if status == "analisado":
        botoes.append([
            {"text": "💰 Precificar", "callback_data": f"precificar_{pncp_id}"},
        ])

    if status == "precificado":
        botoes.append([
            {"text": "🎯 Competitivo", "callback_data": f"competitivo_{pncp_id}"},
            {"text": "📄 Planilha", "callback_data": f"planilha_{pncp_id}"},
        ])

    botoes.append([
        {"text": "⭐ Favoritar", "callback_data": f"favoritar_{pncp_id}"},
        {"text": "💬 Comentar", "callback_data": f"comentar_{pncp_id}"},
    ])
    botoes.append([
        {"text": "⬅️ Voltar", "callback_data": "menu_oportunidades"},
    ])

    return {"inline_keyboard": botoes}


def teclado_relatorios() -> dict:
    """Submenu de relatórios."""
    return {
        "inline_keyboard": [
            [
                {"text": "📈 Resumo Geral", "callback_data": "rel_resumo"},
                {"text": "💵 Custos API", "callback_data": "rel_custos"},
            ],
            [
                {"text": "📊 Por Status", "callback_data": "rel_status"},
                {"text": "🏆 Top Oportunidades", "callback_data": "rel_top"},
            ],
            [
                {"text": "⬅️ Voltar", "callback_data": "menu_principal"},
            ],
        ]
    }


def teclado_config() -> dict:
    """Submenu de configuração."""
    return {
        "inline_keyboard": [
            [
                {"text": "🔄 Status Monitor", "callback_data": "cfg_monitor_status"},
                {"text": "▶️ Iniciar/Parar", "callback_data": "cfg_monitor_toggle"},
            ],
            [
                {"text": "📦 Importar CCTs", "callback_data": "cfg_importar_ccts"},
                {"text": "👥 Concorrentes", "callback_data": "cfg_concorrentes"},
            ],
            [
                {"text": "⬅️ Voltar", "callback_data": "menu_principal"},
            ],
        ]
    }


def teclado_confirmacao(acao: str, pncp_id: str) -> dict:
    """Teclado de confirmação para ações."""
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Confirmar", "callback_data": f"confirmar_{acao}_{pncp_id}"},
                {"text": "❌ Cancelar", "callback_data": "menu_oportunidades"},
            ]
        ]
    }
