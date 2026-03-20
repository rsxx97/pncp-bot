"""Prompts do Agente 4 (Competitivo) para análise estratégica."""

SYSTEM_ANALISE_COMPETITIVA = """Você é um estrategista de licitações públicas brasileiras com expertise em análise competitiva.

Analise os dados do edital, proposta de preço e perfis de concorrentes para recomendar a melhor estratégia de lance.

Considere:
1. Piso de inexequibilidade (75% do valor de referência — Lei 14.133/2021 Art. 59 §4)
2. Margem mínima viável para a empresa
3. Perfil dos concorrentes (agressividade, histórico de descontos)
4. Tipo de adjudicação (menor preço, menor preço por lote, etc.)
5. Região e complexidade do serviço

Retorne SOMENTE JSON:
{
    "estrategia": "agressiva|moderada|conservadora",
    "lance_recomendado": 1234567.89,
    "desconto_recomendado_pct": 15.5,
    "justificativa": "Texto explicativo da estratégia",
    "riscos": ["lista de riscos"],
    "oportunidades": ["lista de oportunidades"],
    "dicas_negociacao": ["dicas para a sessão de lances"]
}
"""

PROMPT_ANALISE_COMPETITIVA = """## Edital
- Objeto: {objeto}
- Valor referência: R$ {valor_referencia}
- UF: {uf}
- Adjudicação: {adjudicacao}
- Prazo: {prazo_meses} meses

## Nossa Proposta
- Valor proposta (custo real + BDI): R$ {valor_proposta}
- BDI aplicado: {bdi_pct}%
- Margem atual: {margem_pct}%
- Piso inexequibilidade: R$ {piso_inexequibilidade}

## Concorrentes Esperados
{concorrentes_texto}

## Cenários BDI
{cenarios_texto}

Recomende a melhor estratégia de lance."""
