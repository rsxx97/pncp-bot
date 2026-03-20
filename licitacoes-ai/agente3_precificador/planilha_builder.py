"""Geração de planilha .xlsx formatada no padrão IN 05/2017."""
import logging
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment, numbers

log = logging.getLogger("planilha_builder")

# Estilos
HEADER_FILL = PatternFill(start_color="1B3A5C", end_color="1B3A5C", fill_type="solid")
HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
EDITAVEL_FILL = PatternFill(start_color="FFFDE7", end_color="FFFDE7", fill_type="solid")
ZEBRA_FILL = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")
TOTAL_FONT = Font(name="Calibri", bold=True, size=11)
THIN_BORDER = Border(
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
    top=Side(style="thin", color="CCCCCC"),
    bottom=Side(style="thin", color="CCCCCC"),
)
BRL_FORMAT = '#,##0.00'
PCT_FORMAT = '0.00%'


def _style_header(ws, row: int, cols: int):
    for col in range(1, cols + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = THIN_BORDER


def _style_row(ws, row: int, cols: int, zebra: bool = False):
    for col in range(1, cols + 1):
        cell = ws.cell(row=row, column=col)
        cell.border = THIN_BORDER
        if zebra:
            cell.fill = ZEBRA_FILL


def _add_modulo_rows(ws, start_row: int, titulo: str, items: list[tuple]) -> int:
    """Adiciona linhas de um módulo. items = [(descricao, valor)]"""
    row = start_row

    # Título do módulo
    ws.cell(row=row, column=1, value=titulo).font = TOTAL_FONT
    row += 1

    for i, (desc, val) in enumerate(items):
        ws.cell(row=row, column=1, value=desc)
        cell = ws.cell(row=row, column=2, value=val)
        cell.number_format = BRL_FORMAT
        _style_row(ws, row, 2, zebra=(i % 2 == 1))
        row += 1

    return row


def gerar_xlsx(
    postos: list[dict],
    cenarios_bdi: list[dict],
    valor_referencia: float = None,
    prazo_meses: int = 12,
    output_path: Path | str = None,
) -> Path:
    """Gera planilha .xlsx completa.

    Args:
        postos: Lista de dicts com dados de cada posto (resultado de calcular_posto_completo)
                Cada dict deve ter: nome, quantidade, e os módulos 1-5
        cenarios_bdi: Resultado do bdi_simulator
        valor_referencia: Valor estimado pelo órgão
        prazo_meses: Prazo do contrato
        output_path: Caminho do arquivo de saída

    Returns:
        Path do arquivo gerado
    """
    wb = Workbook()

    # ── Aba Resumo ────────────────────────────────────
    ws_resumo = wb.active
    ws_resumo.title = "Resumo"
    ws_resumo.column_dimensions["A"].width = 40
    ws_resumo.column_dimensions["B"].width = 18
    ws_resumo.column_dimensions["C"].width = 10
    ws_resumo.column_dimensions["D"].width = 18

    # Header
    for col, header in enumerate(["Posto", "Valor Mensal (R$)", "Qtd", "Subtotal (R$)"], 1):
        ws_resumo.cell(row=1, column=col, value=header)
    _style_header(ws_resumo, 1, 4)

    total_mensal = 0
    row = 2
    for p in postos:
        nome = p.get("nome", "Posto")
        qtd = p.get("quantidade", 1)
        valor = p.get("valor_mensal_posto", 0)
        subtotal = valor * qtd
        total_mensal += subtotal

        ws_resumo.cell(row=row, column=1, value=nome)
        ws_resumo.cell(row=row, column=2, value=valor).number_format = BRL_FORMAT
        ws_resumo.cell(row=row, column=3, value=qtd)
        ws_resumo.cell(row=row, column=4, value=subtotal).number_format = BRL_FORMAT
        _style_row(ws_resumo, row, 4, zebra=(row % 2 == 0))
        row += 1

    # Totais
    row += 1
    ws_resumo.cell(row=row, column=1, value="TOTAL MENSAL").font = TOTAL_FONT
    ws_resumo.cell(row=row, column=4, value=total_mensal).number_format = BRL_FORMAT
    ws_resumo.cell(row=row, column=4).font = TOTAL_FONT
    row += 1

    total_global = total_mensal * prazo_meses
    ws_resumo.cell(row=row, column=1, value=f"TOTAL GLOBAL ({prazo_meses} meses)").font = TOTAL_FONT
    ws_resumo.cell(row=row, column=4, value=total_global).number_format = BRL_FORMAT
    ws_resumo.cell(row=row, column=4).font = TOTAL_FONT

    if valor_referencia:
        row += 2
        ws_resumo.cell(row=row, column=1, value="Valor de referência")
        ws_resumo.cell(row=row, column=4, value=valor_referencia).number_format = BRL_FORMAT
        row += 1
        desconto = (1 - total_global / valor_referencia) * 100 if valor_referencia > 0 else 0
        ws_resumo.cell(row=row, column=1, value="Desconto sobre referência")
        ws_resumo.cell(row=row, column=4, value=f"{desconto:.1f}%")

    # ── Aba por posto ──────────────────────────────────
    for p in postos:
        nome = p.get("nome", "Posto")[:25]
        ws = wb.create_sheet(title=nome)
        ws.column_dimensions["A"].width = 45
        ws.column_dimensions["B"].width = 18

        ws.cell(row=1, column=1, value=f"Detalhamento: {p.get('nome', 'Posto')}")
        ws.cell(row=1, column=1).font = Font(bold=True, size=13)
        row = 3

        # Módulo 1
        m1 = p.get("modulo1", {})
        items = [(k.replace("_", " ").title(), v) for k, v in m1.items() if k != "total_modulo1" and isinstance(v, (int, float))]
        items.append(("TOTAL MÓDULO 1", m1.get("total_modulo1", 0)))
        row = _add_modulo_rows(ws, row, "MÓDULO 1 — Remuneração", items)
        row += 1

        # Módulo 2
        m2 = p.get("modulo2", {})
        items_m2 = [
            ("13º salário", m2.get("decimo_terceiro", 0)),
            ("Férias + 1/3", m2.get("ferias_terco", 0)),
            ("Incidência prev. s/ 13º", m2.get("incidencia_13_prev", 0)),
            ("Incidência prev. s/ férias", m2.get("incidencia_ferias_prev", 0)),
        ]
        sub21 = m2.get("submodulo_2_1", {})
        for k, v in sub21.items():
            if isinstance(v, (int, float)) and k not in ("total_submodulo_2_1", "percentual_total"):
                items_m2.append((f"  {k.replace('_', ' ').title()}", v))
        items_m2.append(("  Total Encargos Prev.", sub21.get("total_submodulo_2_1", 0)))

        sub22 = m2.get("submodulo_2_2", {})
        for k, v in sub22.items():
            if isinstance(v, (int, float)) and k != "total_submodulo_2_2":
                items_m2.append((f"  {k.replace('_', ' ').title()}", v))
        items_m2.append(("  Total Benefícios", sub22.get("total_submodulo_2_2", 0)))
        items_m2.append(("TOTAL MÓDULO 2", m2.get("total_modulo2", 0)))
        row = _add_modulo_rows(ws, row, "MÓDULO 2 — Encargos e Benefícios", items_m2)
        row += 1

        # Módulo 3
        m3 = p.get("modulo3", {})
        items_m3 = [(k.replace("_", " ").title(), v) for k, v in m3.items() if k != "total_modulo3" and isinstance(v, (int, float))]
        items_m3.append(("TOTAL MÓDULO 3", m3.get("total_modulo3", 0)))
        row = _add_modulo_rows(ws, row, "MÓDULO 3 — Provisões Rescisão", items_m3)
        row += 1

        # Módulo 4
        m4 = p.get("modulo4", {})
        items_m4 = [(k.replace("_", " ").title(), v) for k, v in m4.items() if k != "total_modulo4" and isinstance(v, (int, float))]
        items_m4.append(("TOTAL MÓDULO 4", m4.get("total_modulo4", 0)))
        row = _add_modulo_rows(ws, row, "MÓDULO 4 — Reposição Ausências", items_m4)
        row += 1

        # Módulo 5
        m5 = p.get("modulo5", {})
        items_m5 = [
            ("Custos indiretos", m5.get("custos_indiretos", 0)),
            ("Lucro", m5.get("lucro", 0)),
            ("Tributos", m5.get("tributos", 0)),
            ("TOTAL MÓDULO 5", m5.get("total_modulo5", 0)),
        ]
        row = _add_modulo_rows(ws, row, "MÓDULO 5 — CI, Tributos e Lucro", items_m5)
        row += 2

        # Total
        ws.cell(row=row, column=1, value="VALOR MENSAL DO POSTO").font = Font(bold=True, size=12)
        ws.cell(row=row, column=2, value=p.get("valor_mensal_posto", 0)).number_format = BRL_FORMAT
        ws.cell(row=row, column=2).font = Font(bold=True, size=12)

    # ── Aba BDI ────────────────────────────────────────
    ws_bdi = wb.create_sheet(title="Simulador BDI")
    ws_bdi.column_dimensions["A"].width = 30
    ws_bdi.column_dimensions["B"].width = 18
    ws_bdi.column_dimensions["C"].width = 18
    ws_bdi.column_dimensions["D"].width = 18

    headers = ["Métrica", "Agressivo", "Competitivo", "Conservador"]
    for col, h in enumerate(headers, 1):
        ws_bdi.cell(row=1, column=col, value=h)
    _style_header(ws_bdi, 1, 4)

    metricas = [
        ("Custos Indiretos (%)", "ci_pct"),
        ("Lucro (%)", "lucro_pct"),
        ("Tributos (%)", "tributos_pct"),
        ("BDI (%)", "bdi_pct"),
        ("Valor Mensal (R$)", "valor_mensal"),
        ("Valor Global (R$)", "valor_global"),
        ("Desconto s/ referência (%)", "desconto_sobre_referencia_pct"),
        ("Acima inexequibilidade?", "acima_inexequibilidade"),
    ]

    for row_idx, (label, key) in enumerate(metricas, 2):
        ws_bdi.cell(row=row_idx, column=1, value=label)
        for col_idx, cenario in enumerate(cenarios_bdi[:3], 2):
            val = cenario.get(key, "")
            if isinstance(val, bool):
                val = "SIM" if val else "NÃO ⚠️"
            cell = ws_bdi.cell(row=row_idx, column=col_idx, value=val)
            if isinstance(val, float) and "R$" in label:
                cell.number_format = BRL_FORMAT
        _style_row(ws_bdi, row_idx, 4, zebra=(row_idx % 2 == 0))

    # Salvar
    if output_path is None:
        output_path = Path("planilha_custos.xlsx")
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(output_path))
    log.info(f"Planilha salva: {output_path}")
    return output_path
