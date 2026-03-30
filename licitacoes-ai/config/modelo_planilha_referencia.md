# Modelo de Referencia - Planilha de Custos

## Estrutura
- 1 aba por cargo/posto (nome abreviado: ENC_ADM, ASG_PADRAO, etc.)
- Aba RESUMO com quadro consolidado
- Aba BREAK-EVEN com cenarios de lance
- Aba MATERIAIS (quando aplicavel)

## Layout de cada aba de cargo (80 linhas, 4 colunas A-D)
- A1: PLANILHA DE CUSTOS E FORMACAO DE PRECOS
- B2: [ORGAO] [PREGAO] - [Objeto]
- B3: Posto: [nome do posto] | C3: Qtd Postos: | D3: [quantidade]
- B4: Jornada: [44h/12x36/etc] | C4: CCT: | D4: [nome CCT vigente]

### Modulo 1 - Composicao da Remuneracao (linhas 6-11)
- A7: Salario-Base
- A8: Adicional (periculosidade/insalubridade/gratificacao - conforme cargo)
- A9: Adicional Noturno (quando aplicavel)
- A10: Hora Noturna Reduzida (quando aplicavel)
- D11: TOTAL MODULO 1

### Modulo 2 - Encargos e Beneficios
#### 2.1 - 13o, Ferias (linhas 13-16)
- 13o Salario (8.33%)
- Ferias + 1/3 (11.11%)

#### 2.2 - GPS, FGTS (linhas 18-27)
- INSS: 20%
- Sal. Educacao: 2.5%
- SAT: 2% ou 3% (conforme risco do posto)
- SESC: 1.5%, SENAC: 1%, SEBRAE: 0.6%, INCRA: 0.2%
- FGTS: 8%

#### 2.3 - Beneficios (linhas 29-34)
- VT (custo liquido, 22 dias)
- Auxilio-Refeicao/Alimentacao (valor dia x 22 dias)
- BSF (Beneficio Social Familiar - CCT)
- Seguro de Vida (estimativa)

### Modulo 3 - Provisao Rescisao (linhas 42-49)
- API, FGTS s/ API, Multa FGTS s/ API
- APT, GPS/FGTS s/ APT, Multa FGTS s/ APT

### Modulo 4 - Reposicao Profissional Ausente (linhas 51-57)
- Ferias, Ausencias Legais, Licenca-Paternidade
- Acidente Trabalho, Afastamento Maternidade

### Modulo 5 - Insumos Diversos (linhas 59-64)
- Uniformes, Materiais (rateio), Equipamentos, EPIs

### Subtotal Modulos 1-5 (linha 66)

### Modulo 6 - CI, Tributos e Lucro (linhas 68-76)
- CI: 3% (ajustavel)
- Lucro: 3% (ajustavel)
- PIS: conforme regime (Lucro Real c/ creditos = 0.15%)
- COFINS: conforme regime (Lucro Real c/ creditos = 0.69%)
- ISS: 2%
- Tributos calculados "por dentro" do faturamento

### Totais (linhas 78-80)
- Valor total por empregado/mes
- x [postos] = Valor mensal do posto
- Valor anual (12 meses)

## Aba RESUMO
- Quadro com todos os cargos: Item, Cargo, Qtd, Valor Unit/Mes, Valor Mensal, Valor Anual
- Total geral

## Aba BREAK-EVEN
- Cenarios: 3%/3%, 3%/2%, 2%/2%, 2%/1%, 1%/1%, 1%/0%, 0%/0%
- Colunas: CI%, Lucro%, Valor Anual Est., Desconto s/ Ref, Valor Mensal, Status

## Aba MATERIAIS
- Custo mensal total materiais (conforme Anexo do TR)
