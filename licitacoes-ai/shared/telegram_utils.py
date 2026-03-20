"""Helpers de formatação para mensagens Telegram."""
from shared.utils import formatar_valor, formatar_data, truncar_texto

MODALIDADES_NOME = {
    1: "Leilão - Loss",
    2: "Diálogo Competitivo",
    3: "Concurso",
    4: "Concorrência - Loss",
    5: "Concorrência",
    6: "Pregão Eletrônico",
    7: "Pregão Presencial",
    8: "Dispensa de Licitação",
    9: "Inexigibilidade",
    10: "Manifestação de Interesse",
    11: "Pré-qualificação",
    12: "Credenciamento",
    13: "Leilão",
}


def formatar_edital_novo(edital: dict, classificacao: dict | None = None) -> str:
    """Formata notificação de novo edital relevante."""
    score = classificacao.get("score", "?") if classificacao else "?"
    empresa = classificacao.get("empresa_sugerida", "") if classificacao else ""
    justificativa = classificacao.get("justificativa", "") if classificacao else ""
    alertas = classificacao.get("alertas", []) if classificacao else []

    objeto = truncar_texto(edital.get("objeto", ""), 150)
    valor = formatar_valor(edital.get("valor_estimado"))
    abertura = formatar_data(edital.get("data_abertura"))
    uf = edital.get("uf", "?")
    orgao = truncar_texto(edital.get("orgao_nome", ""), 80)
    link = edital.get("link_edital", "")

    msg = (
        f"\U0001f4cb Novo edital relevante (Score: {score}/100)\n\n"
        f"\U0001f3e2 Orgao: {orgao}\n"
        f"\U0001f4dd Objeto: {objeto}\n"
        f"\U0001f4b0 Valor estimado: {valor}\n"
        f"\U0001f4c5 Abertura: {abertura}\n"
        f"\U0001f4cd Local: {uf}\n"
    )

    if empresa:
        msg += f"\U0001f3ed Empresa sugerida: {empresa}\n"

    if justificativa:
        msg += f"\n\U0001f4a1 {justificativa}\n"

    if alertas:
        msg += "\n" + "\n".join(f"\u26a0\ufe0f {a}" for a in alertas)

    if link:
        msg += f"\n\U0001f517 {link}"

    return msg


def formatar_analise(edital: dict, analise: dict) -> str:
    """Formata notificação de análise concluída."""
    parecer = analise.get("parecer", "?")
    emoji = "\u2705" if parecer == "go" else "\u274c" if parecer == "nogo" else "\u26a0\ufe0f"

    objeto = truncar_texto(edital.get("objeto", ""), 100)
    valor = formatar_valor(edital.get("valor_estimado"))
    orgao = truncar_texto(edital.get("orgao_nome", ""), 60)

    msg = (
        f"\U0001f4ca Analise concluida — {emoji} {parecer.upper()}\n\n"
        f"\U0001f3e2 {orgao}\n"
        f"\U0001f4dd {objeto}\n"
        f"\U0001f4b0 Valor: {valor}\n"
    )

    oportunidades = analise.get("oportunidades", [])
    if oportunidades:
        msg += "\n\u2705 Pontos favoraveis:\n"
        msg += "\n".join(f"  - {o}" for o in oportunidades[:3])

    riscos = analise.get("riscos", [])
    if riscos:
        msg += "\n\n\u26a0\ufe0f Riscos:\n"
        msg += "\n".join(f"  - {r}" for r in riscos[:3])

    if parecer == "nogo":
        motivo = analise.get("motivo", "")
        if motivo:
            msg += f"\n\n\U0001f6ab Motivo: {motivo}"

    return msg


def formatar_planilha_pronta(edital: dict, valor_proposta: float, margem: float) -> str:
    """Formata notificação de planilha gerada."""
    objeto = truncar_texto(edital.get("objeto", ""), 100)
    valor_ref = formatar_valor(edital.get("valor_estimado"))
    valor_prop = formatar_valor(valor_proposta)

    msg = (
        f"\U0001f4ca Planilha de custos pronta!\n\n"
        f"\U0001f4dd {objeto}\n"
        f"\U0001f4b0 Referencia: {valor_ref}\n"
        f"\U0001f4b5 Nossa proposta: {valor_prop}\n"
        f"\U0001f4c8 Margem: {margem:.1f}%\n"
    )
    return msg


def formatar_competitivo(edital: dict, lance: dict) -> str:
    """Formata notificação do dossiê competitivo."""
    objeto = truncar_texto(edital.get("objeto", ""), 100)
    valor_ref = formatar_valor(edital.get("valor_estimado"))

    msg = (
        f"\U0001f3af Dossie competitivo pronto\n\n"
        f"\U0001f4dd {objeto}\n"
        f"\U0001f4b0 Referencia: {valor_ref}\n\n"
        f"\U0001f3c6 Sugestao de lance:\n"
        f"  {formatar_valor(lance.get('lance_sugerido'))}\n"
        f"  Margem: {lance.get('margem_sugerida_pct', 0):.1f}%\n\n"
        f"\u26a1 Piso: {formatar_valor(lance.get('lance_minimo'))}\n"
        f"\U0001f53c Teto: {formatar_valor(lance.get('lance_maximo'))}\n"
    )

    concorrentes = lance.get("concorrentes_esperados", [])
    if concorrentes:
        msg += "\n\U0001f465 Concorrentes esperados:\n"
        msg += "\n".join(f"  - {c}" for c in concorrentes[:5])

    return msg
