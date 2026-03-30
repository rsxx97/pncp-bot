"""Teste de análise da NUCLEP."""
import sys, json, logging, re
logging.basicConfig(level=logging.WARNING)
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from agente2_analista.pdf_extractor import extract_smart
from agente2_analista.prompts import SYSTEM_EDITAL_PARSER, build_user_prompt_analise
from shared.llm_client import ask_claude

DIR = 'data/editais'
edital = extract_smart(f'{DIR}/42515882000330-2026-7_EDITAL_PE-003-2026.pdf')
tr = extract_smart(f'{DIR}/42515882000330-2026-7_TERMO_DE_REFERENCIA_-_PE_003-2026.pdf')
user_prompt = build_user_prompt_analise(edital['text'], tr['text'])

print(f'Edital: {edital["pages"]} pgs | TR: {tr["pages"]} pgs | Prompt: {len(user_prompt)} chars')
print('Chamando Haiku...')

resp = ask_claude(system=SYSTEM_EDITAL_PARSER, user=user_prompt, agente='agente2', max_tokens=4000)

# Strip markdown wrapper
clean = resp.strip()
if clean.startswith('```'):
    clean = re.sub(r'^```(?:json)?\s*\n?', '', clean)
    clean = re.sub(r'\n?```\s*$', '', clean)

# Tenta parse; se falhar, trunca no último } válido
try:
    data = json.loads(clean)
except json.JSONDecodeError:
    # Encontra o JSON principal
    depth = 0
    end = 0
    for i, c in enumerate(clean):
        if c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    data = json.loads(clean[:end])

print(f'\n=== RESULTADO ===')
print(f'Objeto: {data.get("objeto_resumido")}')
print(f'Valor: {data.get("valor_estimado")}')
print(f'Parecer: {data.get("parecer")}')
print(f'Motivo: {str(data.get("motivo_parecer",""))[:100]}')

postos = data.get('postos_trabalho', [])
print(f'\nPostos: {len(postos)}')
for p in postos:
    sal = p.get('salario_base', '?')
    insalub = p.get('adicional_insalubridade_pct', 0)
    print(f'  {p["funcao"]} x{p["quantidade"]} | {p["jornada"]} | sal=R${sal} | insalub={insalub}%')

cct = data.get('cct', {})
print(f'\nCCT: {cct.get("sindicato_patronal")} x {cct.get("sindicato_laboral")}')
for pi in cct.get('pisos_mencionados', []):
    print(f'  Piso: {pi["funcao"]} R$ {pi.get("valor","?")}')
ben = cct.get('beneficios', {})
print(f'  VA: {ben.get("vale_alimentacao")} | VT: {ben.get("vale_transporte")} | BSF: {ben.get("beneficio_social_familiar")}')

print(f'\nSAT/RAT: {data.get("sat_rat_pct")}% | ISS: {data.get("iss_municipio_pct")}%')
print(f'Riscos: {data.get("riscos", [])}')

# Salva para uso posterior
with open('data/test_analise_nuclep.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print('\nSalvo em data/test_analise_nuclep.json')
