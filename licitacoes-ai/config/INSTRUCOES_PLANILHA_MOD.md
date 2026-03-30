# INSTRUÇÕES PARA MONTAGEM DE PLANILHA DE CUSTOS E FORMAÇÃO DE PREÇOS — CONTRATOS DE MÃO DE OBRA DEDICADA (MOD)

## VISÃO GERAL

Quando o edital tratar de **prestação de serviços com dedicação exclusiva de mão de obra** (postos de trabalho fixos), você DEVE seguir rigorosamente estas instruções para montar a Planilha de Custos e Formação de Preços (PCFP).

### Como identificar um contrato de MOD:
- O edital menciona "dedicação exclusiva de mão de obra"
- O edital lista "postos de trabalho" com quantitativos
- O edital exige "Planilha de Custos e Formação de Preços" no modelo IN 05/2017
- O edital veda Simples Nacional (cessão de mão de obra, art. 17 XII LC 123/06)
- O edital menciona Módulos 1 a 6

### Características de MOD (validação de sanidade):
- Margem bruta típica: **3% a 10%**. Se > 15%, há erro de cálculo.
- Valor por empregado/mês típico: **R$ 3.500 a R$ 8.000** para funções administrativas básicas.
- O break-even (CI=0/Lucro=0) nunca deve ser inferior a 70% do teto do edital. Se for, há erro.
- Desconto máximo sustentável em MOD: tipicamente **8% a 15%**. Se > 25%, revisar.

---

## ETAPA 0: LEITURA ESTRUTURADA DO EDITAL E ANEXOS (OBRIGATÓRIA — EXECUTAR PRIMEIRO)

Esta é a etapa mais crítica. Erros aqui se propagam para toda a planilha. Siga a ordem abaixo sem pular nenhum passo.

### 0.1 Ler o Edital Principal
O edital principal contém:
- **Objeto** da contratação (item 1): identificar se é MOD
- **Tabela de itens/lotes** (item 1.2 ou similar): TODOS os cargos, quantitativos de postos, valores estimados unitários e totais
- **Valor total estimado**: o TETO da licitação
- **Data da sessão**: para saber o prazo
- **Critério de julgamento**: menor preço global, por lote, por item
- **Lista de anexos**: identificar quais anexos existem e seus números SEI

**AÇÃO**: Extrair a tabela completa de itens e anotar o valor teto. Listar todos os anexos mencionados.

### 0.2 Localizar e Ler o Termo de Referência (TR)
O TR é o documento mais importante para precificação. Ele contém:
- **Descrição detalhada dos cargos** com atribuições e capacitação mínima
- **Jornadas de trabalho** por cargo (44h, 30h, 12x36, etc.)
- **CCT aplicável** ou orientação sobre qual CCT usar
- **Uniformes obrigatórios**: lista de peças por cargo, quantidade, periodicidade de reposição
- **Materiais e equipamentos** a serem fornecidos pela contratada
- **Requisitos de habilitação técnica**: atestados mínimos (ex: "20 postos de secretariado")
- **Local de execução**
- **Vedação ao Simples Nacional**

**AÇÃO**: Extrair para cada cargo: jornada, escolaridade, uniformes (com custo estimado), materiais/equipamentos. Anotar a CCT referenciada.

**ONDE ENCONTRAR O TR**: 
- Pode estar no mesmo PDF do edital (como anexo)
- Pode ser um PDF separado nos anexos do edital no SIGA/PNCP
- No PNCP, verificar todos os arquivos anexos à compra
- O edital lista "Anexo I - Termo de Referência" com número SEI

### 0.3 Localizar e Ler a Planilha de Custos Modelo (Anexo I.A ou similar)
A planilha modelo define a ESTRUTURA EXATA que o órgão espera receber. Ela pode ter:
- Módulos 1 a 6 com linhas pré-definidas
- Campos específicos (CBO, CCT, data-base)
- Quadro-resumo com formato próprio
- Fórmulas ou campos calculados

**AÇÃO**: Se a planilha modelo existir (geralmente em .xlsx), USAR A MESMA ESTRUTURA. Não inventar layout próprio. Preencher o modelo do órgão.

**ONDE ENCONTRAR**:
- "Anexo I.A - Planilha de Custos e Formação de Preços" (SEFAZ/RJ usa esse nome)
- Pode ser referenciada por número SEI no TR (ex: "SEI 106423586")
- Baixar do SIGA ou PNCP junto com os demais anexos

### 0.4 Localizar e Ler o Orçamento Estimado (Anexo V ou similar)
O orçamento estimado mostra como o órgão chegou no valor teto. Ele revela:
- Composição de custos unitários usada como referência
- Salários e encargos que o órgão considerou
- BDI/CI/Lucro que o órgão aplicou
- Fontes de pesquisa de preços (Painel de Preços, contratos anteriores, etc.)

**AÇÃO**: Comparar o orçamento estimado com a sua planilha. Se houver divergência grande (>10%), investigar a causa.

### 0.5 Verificar outros Anexos relevantes
- **Acordo de Nível de Serviço (ANS)**: pode prever glosas que impactam o faturamento
- **Estimativa de Materiais e Equipamentos**: lista detalhada com quantidades
- **Modelo de Proposta**: formato exato para apresentação do lance
- **Minuta de Contrato**: cláusulas de repactuação, garantia, pagamento

### 0.6 Checklist de Extração (não prosseguir sem completar)
Antes de ir para a Etapa 1, confirmar que você tem:
- [ ] Tabela completa de cargos e postos do edital
- [ ] Valor teto total da licitação
- [ ] Jornada de trabalho de cada cargo (do TR)
- [ ] CCT aplicável identificada
- [ ] Lista de uniformes por cargo com periodicidade (do TR)
- [ ] Lista de materiais/equipamentos (do TR)
- [ ] Requisitos de habilitação técnica (atestados)
- [ ] Planilha modelo do órgão (se disponível)
- [ ] Regime tributário vedado (Simples Nacional vedado?)
- [ ] Local de execução (impacta ISS e VT)

**SE FALTAR ALGUM ITEM**: Buscar nos anexos do edital no SIGA/PNCP. Se não encontrar, sinalizar ao usuário antes de prosseguir.

---

## ETAPA 1: EXTRAÇÃO COMPLETA DO EDITAL

### 1.1 Extrair TODOS os cargos/itens
Ler a tabela do edital (geralmente item 1.2 ou 2.2) e listar TODOS os cargos com:
- Nome do cargo
- Quantidade de postos
- Local de execução

**VALIDAÇÃO OBRIGATÓRIA**: Conferir que a soma dos postos extraídos bate com o "quantitativo total de postos" informado no edital. Se não bater, você está faltando cargos.

### 1.2 Extrair jornadas de trabalho
Para cada cargo, identificar a jornada no Termo de Referência ou ETP:
- **44h/sem** (padrão CLT) = 220h/mês — maioria dos cargos
- **30h/sem** (telefonista, art. 227 CLT) = 150h/mês ou 180h/mês
- **36h/sem** (alguns técnicos)
- **12x36** (vigilância, portaria noturna)

### 1.3 Extrair requisitos de habilitação técnica
- Quantidade mínima de postos em atestados
- Funções específicas exigidas nos atestados
- Isso impacta qual empresa do grupo pode participar

### 1.4 Extrair exigências de uniformes e materiais
- Ler a seção de uniformes do TR: itens por cargo, quantidade, periodicidade de reposição
- Ler a seção de materiais/equipamentos
- Calcular custo mensal por empregado

---

## ETAPA 2: IDENTIFICAR CCT E SALÁRIOS

### 2.1 CCT aplicável
O TR geralmente indica a CCT. Para o estado do Rio de Janeiro, as principais são:

| Tipo de serviço | CCT | Sindicatos | Data-base |
|---|---|---|---|
| Limpeza, conservação, apoio administrativo, copeiragem, recepção, secretariado | SEAC-RJ | SEAC-RJ x SIEMACO-RIO | 01/03 |
| Vigilância | SINDVIG-RJ | Patronal x SINTRAVIG | variável |
| Motoristas | SINTRUCAD-RIO | Patronal x SINTRUCAD | variável |

### 2.2 Pisos salariais CCT SEAC-RJ 2025/2026 (RJ001061/2025)
Vigência: 01/03/2025 a 28/02/2026

| Função | Piso |
|---|---|
| Servente / Aux. Serviços Gerais / Copeira / Faxineira / Limpador | R$ 1.730,75 |
| Aux. Portaria | R$ 1.741,24 |
| Recepcionista / Aux. Almoxarife / Aux. Jardinagem / Manobrista | R$ 1.837,87 |
| Porteiro / Vigia Terceirizado / Zelador | R$ 1.917,71 |
| Operador Máq. Limpeza Tripulada | R$ 2.021,66 |
| Assistente Administrativo | R$ 2.017,51 |
| Agente Administrativo / Digitador | R$ 2.136,83 |
| Encarregado | R$ 2.161,45 |
| Téc. Secretariado | R$ 2.250,19 |
| Ass. Administrativo Pleno | R$ 2.338,69 |
| Garçom / Almoxarife | R$ 2.465,73 |
| Cozinheira | R$ 2.351,66 |
| Ass. Administrativo Sênior | R$ 2.672,34 |
| Chefe de Departamento | R$ 3.541,52 |
| Supervisor / Enfermeira Supervisora | R$ 4.418,12 |
| Recepcionista Pleno (bilíngue) | R$ 2.958,60 |
| Recepcionista Sênior (trilíngue) | R$ 3.569,53 |

**Funções não listadas**: Cláusula 7ª da CCT diz que funções de liderança não listadas recebem piso de encarregado; funções sem liderança e sem qualificação técnica recebem piso de servente.

### 2.3 Benefícios CCT SEAC-RJ 2025/2026

| Benefício | Valor | Base |
|---|---|---|
| Auxílio Alimentação/Refeição | R$ 25,00/dia | Dias efetivamente trabalhados |
| Desconto VA do empregado | 10% do total | Desconta do custo |
| Vale-Transporte | Tarifa vigente x 2 x dias úteis | Desconto de 6% do salário |
| Tarifa VT Rio de Janeiro (ref.) | R$ 4,70 (ônibus BRT/convencional) | Verificar tarifa atualizada |
| Seguro de vida | Conforme cláusula CCT | Verificar valor vigente |

---

## ETAPA 3: DADOS DA EMPRESA

### 3.1 Dados tributários por empresa do grupo

| Empresa | Regime | PIS efetivo | COFINS efetiva | ISS | SAT/RAT |
|---|---|---|---|---|---|
| Manutec | Lucro Real | 0,05% | 4,15% | 2,00% | 2% |
| Miami Segurança e Serviços | Lucro Real | 0,05% | 4,15% | 2,00% | 2% |
| Blue Soluções Corporativas | Lucro Real | verificar | verificar | 2,00% | verificar |
| GB Engenharia | verificar | verificar | verificar | verificar | verificar |

**IMPORTANTE**: Usar alíquotas EFETIVAS (com créditos), não nominais. PIS nominal é 1,65% e COFINS nominal é 7,60% no Lucro Real, mas com créditos o efetivo é muito menor.

### 3.2 Sanções ativas
- **Manutec**: Sanção AGU ativa até ~meados 2026. NÃO pode participar de licitações.
- Sempre verificar CEIS, CNEP, TCE/RJ antes de sugerir empresa.

---

## ETAPA 4: MONTAGEM DA PLANILHA (MÓDULOS 1 A 6)

A planilha deve ter **UMA ABA POR CARGO** + aba RESUMO + aba BREAK-EVEN.

**SE EXISTE PLANILHA MODELO DO ÓRGÃO (Anexo I.A)**: Usar a estrutura do modelo. Apenas preencher os valores. Não alterar linhas, colunas ou layout.

**SE NÃO EXISTE PLANILHA MODELO**: Usar a estrutura padrão IN 05/2017 abaixo.

### MÓDULO 1 — Composição da Remuneração

| Linha | Descrição | Cálculo |
|---|---|---|
| A | Salário Base | Piso da CCT para a função |
| B | Adicional de periculosidade | 30% do salário base (se aplicável) |
| C | Adicional de insalubridade | 20% ou 40% do piso servente (se aplicável, conforme CCT) |
| D | Adicional noturno | 20% sobre hora base, pro rata das horas noturnas |
| E | Adicional hora noturna reduzida | Diferença 60min→52:30 nas horas noturnas |
| **TOTAL** | | Soma A a E |

### MÓDULO 2 — Encargos e Benefícios

#### Submódulo 2.1 — 13º Salário, Férias e Adicional

| Linha | Descrição | Cálculo |
|---|---|---|
| A | 13º Salário | Remuneração (Mód.1) / 12 |
| B | Férias + 1/3 | Remuneração (Mód.1) / 12 × 4/3 |
| **TOTAL 2.1** | | A + B |

#### Submódulo 2.2 — GPS, FGTS e Outras Contribuições

**Base de incidência = Módulo 1 + Submódulo 2.1**

| Linha | Descrição | % | Valor |
|---|---|---|---|
| A | INSS | **20,00%** | Base × 20% |
| B | Salário Educação | 2,50% | Base × 2,5% |
| C | SAT/RAT | **verificar por empresa** (1%, 2% ou 3%) | Base × SAT% |
| D | SESC | 1,50% | Base × 1,5% |
| E | SENAC | 1,00% | Base × 1% |
| F | SEBRAE | 0,60% | Base × 0,6% |
| G | INCRA | 0,20% | Base × 0,2% |
| H | FGTS | 8,00% | Base × 8% |
| **TOTAL 2.2** | | **~35,80%** | Soma |

**⚠ ATENÇÃO: INSS patronal é SEMPRE 20%. Nunca 10%. Erro de INSS a 10% subestima o custo em ~R$ 200/empregado/mês.**

#### Submódulo 2.3 — Benefícios Mensais e Diários

| Linha | Descrição | Cálculo |
|---|---|---|
| A | Vale-Transporte | (Tarifa × 2 × dias úteis) − (6% × salário base). Se negativo, usar zero. |
| B | Auxílio-Alimentação | (R$ 25,00 × dias úteis) − 10% desconto empregado |
| C | Outros benefícios CCT | Seguro de vida, assistência, etc. conforme CCT |
| **TOTAL 2.3** | | Soma |

**Dias úteis padrão: 22 dias/mês**

#### Resumo Módulo 2
TOTAL MÓDULO 2 = Total 2.1 + Total 2.2 + Total 2.3

### MÓDULO 3 — Provisão para Rescisão

Premissa padrão: turnover 5% ao ano, 50% sem justa causa → taxa de incidência = 1,94%

| Linha | Descrição | Cálculo |
|---|---|---|
| A | Aviso prévio indenizado | Remuneração × 1,94% |
| B | Incidência FGTS sobre API | Linha A × 8% |
| C | Multa FGTS do API | (Rem + 13º + férias+1/3) × 8% × 40% × 1,94% |
| D | Aviso prévio trabalhado | (Rem / 30 × 7 dias) × 1,94% |
| E | Incidência Submód 2.2 sobre APT | Linha D × alíquota total do 2.2 |
| F | Multa FGTS do APT | (Rem + 13º + férias+1/3) × 8% × 40% × 1,94% |
| **TOTAL** | | Soma A a F |

### MÓDULO 4 — Custo de Reposição do Profissional Ausente

#### Submódulo 4.1 — Ausências Legais

| Linha | Descrição | Cálculo |
|---|---|---|
| A | Férias (substituto) | Remuneração / 12 |
| B | Ausências legais | Remuneração / 365 × 3 dias |
| C | Licença-paternidade | Remuneração / 365 × 5 dias × 2% probabilidade |
| D | Afastamento maternidade | Remuneração / 365 × 120 dias × 2% probabilidade |
| **TOTAL 4.1** | | Soma |

#### Submódulo 4.2 — Intrajornada
- Para jornadas diurnas de 44h com intervalo de 1h: geralmente zero (intervalo não remunerado)
- Para 12x36: pode haver custo de intrajornada

**TOTAL MÓDULO 4** = Total 4.1 + Total 4.2

### MÓDULO 5 — Insumos Diversos

| Linha | Descrição | Cálculo |
|---|---|---|
| A | Uniformes | Custo dos itens listados no TR ÷ periodicidade (geralmente semestral = ÷6 para mensal) |
| B | Materiais | Conforme TR (materiais de limpeza, descartáveis, etc.) |
| C | Equipamentos | Conforme TR (headsets, EPIs, etc.) ÷ periodicidade |
| **TOTAL** | | Soma |

**CÁLCULO DO SUBTOTAL**: Módulo 1 + Módulo 2 + Módulo 3 + Módulo 4 + Módulo 5

### MÓDULO 6 — Custos Indiretos, Tributos e Lucro

| Linha | Descrição | % | Cálculo |
|---|---|---|---|
| A | Custos Indiretos (CI) | variável (1% a 5%) | Subtotal × CI% |
| B | Lucro | variável (1% a 5%) | Subtotal × Lucro% |
| C | Tributos | calculado | Ver fórmula abaixo |

**Fórmula dos tributos (cálculo "por dentro"):**
```
Base pré-tributos = Subtotal + CI + Lucro
Faturamento = Base pré-tributos / (1 − alíquota total tributos)
Tributos = Faturamento − Base pré-tributos

Alíquota total tributos = PIS% + COFINS% + ISS%
```

**VALOR MENSAL POR EMPREGADO** = Subtotal + Módulo 6

---

## ETAPA 5: ABA RESUMO

Criar aba com tabela consolidada:

| Item | Cargo | Postos | R$/Emp/Mês | R$ Mensal | R$ Anual |
|---|---|---|---|---|---|
| 1 | [cargo] | [postos] | [valor] | [valor × postos] | [× 12] |
| ... | | | | | |
| **TOTAL** | | **[soma postos]** | | **[soma mensal]** | **[soma anual]** |

Incluir também:
- Teto do edital (anual)
- Nossa proposta (anual)
- Desconto sobre o teto (%)
- Margem disponível (R$)

---

## ETAPA 6: ABA BREAK-EVEN (OBRIGATÓRIA)

### 6.1 Break-even por cargo
Calcular o custo de cada cargo com CI=0% e Lucro=0%. Este é o custo puro — abaixo dele é prejuízo.

### 6.2 Simulador de cenários
Montar tabela com os seguintes cenários:

| Cenário | CI% | Lucro% | Valor Anual | Desconto s/ Teto | Margem Bruta/ano | Margem/mês | Status |
|---|---|---|---|---|---|---|---|
| Conservador | 3% | 3% | calc | calc | calc | calc | ver regra |
| Moderado | 2,5% | 2,5% | calc | calc | calc | calc | ver regra |
| Agressivo | 2% | 2% | calc | calc | calc | calc | ver regra |
| Muito agressivo | 1,5% | 1,5% | calc | calc | calc | calc | ver regra |
| Mínimo | 1% | 1% | calc | calc | calc | calc | ver regra |
| Ultra-mínimo | 0,5% | 0,5% | calc | calc | calc | calc | ver regra |
| BREAK-EVEN | 0% | 0% | calc | calc | R$ 0 | R$ 0 | ⛔ LIMITE |

### 6.3 Status por faixa

| Margem/mês | Status |
|---|---|
| > R$ 10.000 | ✅ CONFORTÁVEL |
| R$ 5.000 a R$ 10.000 | ✅ VIÁVEL |
| R$ 1.500 a R$ 5.000 | ⚡ AGRESSIVO |
| < R$ 1.500 | ⚠ RISCO ALTO |
| R$ 0 | ⛔ BREAK-EVEN |

### 6.4 Resumo estratégico
Exibir com destaque:
- Lance inicial sugerido (CI 3%/3%)
- Lance competitivo (CI 2%/2%)
- PISO ABSOLUTO (break-even)
- Piso de inexequibilidade (50% do teto)
- Desconto máximo sustentável (%)
- Valor mínimo absoluto (anual e mensal)

---

## VALIDAÇÕES OBRIGATÓRIAS (EXECUTAR ANTES DE ENTREGAR)

1. ✅ O edital foi lido e o objeto identificado corretamente?
2. ✅ O Termo de Referência foi localizado e lido?
3. ✅ A planilha modelo do órgão foi buscada nos anexos?
4. ✅ Todos os cargos do edital foram precificados?
5. ✅ Quantitativo de postos confere com o edital?
6. ✅ Salários são da CCT vigente (não estimados)?
7. ✅ INSS está a 20% (não 10%)?
8. ✅ Base do Submódulo 2.2 inclui Módulo 1 + Submódulo 2.1?
9. ✅ Tributos são as alíquotas efetivas da empresa?
10. ✅ Simples Nacional está vedado?
11. ✅ Break-even > 70% do teto? (se não, há erro)
12. ✅ Margem < 15%? (se não, revisar classificação do contrato)
13. ✅ Empresa sugerida está sem sanções ativas?

---

## FORMATO DA PLANILHA XLSX

### Abas obrigatórias:
1. Uma aba por cargo (ex: ENCARREGADO, COPEIRA, RECEPCIONISTA, etc.)
2. Aba RESUMO (consolidado + comparação com teto)
3. Aba BREAK-EVEN (cenários de lance)

### Formatação:
- Cabeçalhos de módulo: fundo azul escuro (#002060 ou #4472C4), fonte branca, negrito
- Subcabeçalhos: fundo azul claro (#D6E4F0), negrito
- Totais parciais: fundo azul claro
- Subtotal geral: fundo amarelo (#FFFF00)
- Valor por empregado: fundo verde (#92D050)
- Break-even: fundo vermelho (#FF6B6B)
- Valores monetários: formato #,##0.00
- Percentuais: formato 0.00%
- Colunas: A (letra/número), B (descrição ~50 chars), C (percentual ~12 chars), D (valor ~16 chars)
