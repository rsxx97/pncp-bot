"""Insere editais do calendario no banco."""
import sqlite3
from datetime import datetime

db = sqlite3.connect('data/licitacoes.db')
now = datetime.now().isoformat()

editais = [
    # 23 MARCO
    {"pncp_id": "MANUAL-PMDC-003", "orgao_nome": "PMDC", "objeto": "CONTRATACAO DE EMPRESA ESPECIALIZADA PARA EXECUCAO DE OBRAS DE INFRAESTRUTURA URBANA - EXIGE BALANCO DOS 2 ULTIMOS EXERCICIOS E ATESTADO TECNICO", "valor_estimado": 8600000, "uf": "RJ", "modalidade": "Concorrencia", "data_abertura": "2026-03-23", "fonte": "manual", "score_relevancia": 75, "empresa_sugerida": "manutec"},
    # 24 MARCO
    {"pncp_id": "MANUAL-PMJS-042", "orgao_nome": "PMJS/SC", "objeto": "SERVICOS DE ENGENHARIA PARA PAVIMENTACAO ASFALTICA, TERRAPLENAGEM, DRENAGEM PLUVIAL E SINALIZACAO VIARIA (VILA BAEPENDI - 1.010,59m) - ATESTADO MIN 50% ITENS RELEVANTES + ACERVO CREA/CAU - BALANCO 2 ULTIMOS EXERCICIOS", "valor_estimado": 2145575.39, "uf": "SC", "modalidade": "Concorrencia", "data_abertura": "2026-03-24T08:00", "fonte": "manual", "score_relevancia": 60, "empresa_sugerida": "manutec"},
    {"pncp_id": "MANUAL-SEPOL-003", "orgao_nome": "SEPOL/RJ", "objeto": "REGISTRO DE PRECOS PARA AQUISICAO DE APARELHOS DE AR-CONDICIONADO (JANELA E SPLIT INVERTER) PARA UNIDADES DA POLICIA CIVIL - ATESTADO + EXPERIENCIA MIN 20%", "valor_estimado": 7672892.44, "uf": "RJ", "modalidade": "Pregao Eletronico", "data_abertura": "2026-03-24T10:00", "fonte": "comprasrj", "score_relevancia": 50, "empresa_sugerida": ""},
    {"pncp_id": "MANUAL-PMBLUMENAU-026", "orgao_nome": "PM BLUMENAU/SC", "objeto": "PAVIMENTACAO EM LAJOTA SEXTAVADA E DRENAGEM PLUVIAL NA RUA LEOPOLDO HERINGER (BAIRRO PROGRESSO) - ATESTADO CREA/CAU - BALANCO ULTIMO EXERCICIO - GARANTIA DE PROPOSTA", "valor_estimado": 2560041.48, "uf": "SC", "modalidade": "Concorrencia", "data_abertura": "2026-03-24T09:00", "fonte": "comprasbr", "score_relevancia": 55, "empresa_sugerida": "manutec"},
    {"pncp_id": "MANUAL-SEFAZ-005", "orgao_nome": "SEFAZ/RJ", "objeto": "SERVICOS CONTINUOS DE APOIO ADMINISTRATIVO - ATESTADOS DE GESTAO DE MAO DE OBRA COM EXPERIENCIA MIN 3 ANOS E COMPROVACAO DE 20 POSTOS DE SECRETARIADO E 10 DE RECEPCAO (ACEITA SOMATORIO)", "valor_estimado": 3680743.94, "uf": "RJ", "modalidade": "Pregao Eletronico", "data_abertura": "2026-03-24T11:00", "fonte": "comprasnet", "score_relevancia": 90, "empresa_sugerida": "blue"},
    {"pncp_id": "MANUAL-PMPALHOCA-026", "orgao_nome": "PM PALHOCA/SC", "objeto": "EXECUCAO DE GRAMADO SINTETICO E REFORMA DE ALAMBRADOS EM QUADRA (BAIRRO PACHECOS) COM FORNECIMENTO DE MATERIAL E MAO DE OBRA - ATESTADO + CAT + BALANCO 2 EXERCICIOS + GARANTIA CONTRATO", "valor_estimado": 363878.68, "uf": "SC", "modalidade": "Concorrencia", "data_abertura": "2026-03-24T13:30", "fonte": "compraspublicas", "score_relevancia": 45, "empresa_sugerida": ""},
    {"pncp_id": "MANUAL-SME-SMO-004", "orgao_nome": "SME/SAO MIGUEL DO OESTE/SC", "objeto": "REFORMA E AMPLIACAO DO GINASIO JOAO CASSOL (EMEIEF TEONISIO WAGNER) - ATESTADO EMPRESA E RESPONSAVEL TECNICO + CREA/CAU - BALANCO 2 EXERCICIOS", "valor_estimado": 1021067.35, "uf": "SC", "modalidade": "Concorrencia Eletronica", "data_abertura": "2026-03-24T13:00", "fonte": "comprasnet", "score_relevancia": 55, "empresa_sugerida": "manutec"},
    {"pncp_id": "MANUAL-CMRJ-90004", "orgao_nome": "CMRJ", "objeto": "PRESTACAO DE SERVICOS DE OPERACAO DA RIO TV CAMARA - EQUIPE ESPECIALIZADA PRODUCAO, REPORTAGENS, EDICAO, BROADCAST, STREAMING E SUPORTE TECNICO - ATESTADO MIN 50% DO OBJETO POR 3 ANOS (SOMA ATESTADOS) - BALANCO 2 EXERCICIOS - GARANTIA 2%", "valor_estimado": None, "uf": "RJ", "modalidade": "Pregao Eletronico", "data_abertura": "2026-03-24T14:00", "fonte": "comprasnet", "score_relevancia": 70, "empresa_sugerida": "blue"},
    {"pncp_id": "MANUAL-CMI-90004", "orgao_nome": "CMI/RJ", "objeto": "PRESTACAO DE SERVICOS DE SEGURANCA E MEDICINA DO TRABALHO - BALANCO 2 ULTIMOS EXERCICIOS - NAO ADMITE SUBCONTRATACAO - REGISTRO NOS CONSELHOS COMPETENTES", "valor_estimado": 280000, "uf": "RJ", "modalidade": "Pregao Eletronico", "data_abertura": "2026-03-24T10:00", "fonte": "comprasnet", "score_relevancia": 80, "empresa_sugerida": "miami"},
    {"pncp_id": "MANUAL-SEFAZ-90005", "orgao_nome": "SEFAZ/RJ", "objeto": "SERVICOS CONTINUADOS DE LIMPEZA E CONSERVACAO - EXIGE BALANCO E ATESTADO DE CAPACIDADE TECNICA", "valor_estimado": 3200000, "uf": "RJ", "modalidade": "Pregao Eletronico", "data_abertura": "2026-03-24", "fonte": "comprasrj", "score_relevancia": 95, "empresa_sugerida": "manutec"},
    {"pncp_id": "MANUAL-REURB-001", "orgao_nome": "REURB", "objeto": "SERVICOS TECNICOS DE REGULARIZACAO FUNDIARIA URBANA - EXIGE GARANTIA DE PROPOSTA E EXPERIENCIA COMPROVADA", "valor_estimado": 1100000, "uf": "RJ", "modalidade": "Pregao Eletronico", "data_abertura": "2026-03-24", "fonte": "manual", "score_relevancia": 70, "empresa_sugerida": "manutec"},
    {"pncp_id": "MANUAL-CASS-90002", "orgao_nome": "CASS", "objeto": "SERVICOS DE LIMPEZA E CONSERVACAO - EXIGE BALANCO DOS 2 ULTIMOS EXERCICIOS", "valor_estimado": 740000, "uf": "RJ", "modalidade": "Pregao Eletronico", "data_abertura": "2026-03-24", "fonte": "manual", "score_relevancia": 85, "empresa_sugerida": "manutec"},
    {"pncp_id": "MANUAL-SMHRF-PARATY", "orgao_nome": "SMHRF/PARATY", "objeto": "SERVICOS DE REGULARIZACAO FUNDIARIA - EXIGE EXPERIENCIA COMPROVADA", "valor_estimado": 1250000, "uf": "RJ", "modalidade": "Pregao Eletronico", "data_abertura": "2026-03-24", "fonte": "manual", "score_relevancia": 68, "empresa_sugerida": "manutec"},
    {"pncp_id": "MANUAL-BFROXO-90006", "orgao_nome": "PREFEITURA DE BELFORD ROXO", "objeto": "SERVICOS CONTINUADOS DE LIMPEZA URBANA - EXIGE BALANCO DOS 2 ULTIMOS EXERCICIOS E ATESTADO TECNICO", "valor_estimado": 6900000, "uf": "RJ", "modalidade": "Pregao Eletronico", "data_abertura": "2026-03-24", "fonte": "manual", "score_relevancia": 92, "empresa_sugerida": "manutec"},
]

for ed in editais:
    cols = list(ed.keys()) + ["status", "created_at", "updated_at"]
    vals = list(ed.values()) + ["novo", now, now]
    placeholders = ",".join(["?"] * len(cols))
    col_names = ",".join(cols)
    db.execute(f"INSERT OR IGNORE INTO editais ({col_names}) VALUES ({placeholders})", vals)

db.commit()
print(f"{len(editais)} editais cadastrados")

db.row_factory = sqlite3.Row
rows = db.execute("SELECT pncp_id, orgao_nome, valor_estimado, uf, data_abertura FROM editais ORDER BY data_abertura").fetchall()
for r in rows:
    v = f"R${r['valor_estimado']:,.0f}" if r["valor_estimado"] else "N/I"
    print(f"  {r['uf']:3} {r['orgao_nome'][:28]:28} {v:>15}  {r['data_abertura'] or ''}")
