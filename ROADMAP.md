# 🗺️ Roadmap — Sistema de Licitações GB Group

Última atualização: 2026-04-30

## 📊 Estado atual

### Bots por nicho operacionais

| Nicho | Cliente | Canal Telegram | UF | Status | Disparados (1ª rodada) |
|---|---|---|---|---|---|
| 🏗 Obra / Reforma / Manutenção Predial | B7 + Manutec | "Construção - Manutenção Predial" | SC + RJ | ✅ Ativo | **233 editais** |
| 💻 Aquisição TI / Eletrônicos | (a definir) | "Aquisição TI/Eletrônicos - RJ" | RJ | ✅ Ativo | **33 editais** |
| ♻️ Resíduos | São Lourenço | SL-Resíduos | RJ | ✅ Ativo | (operando há semanas) |
| 🛡 Vigilância / Segurança | Miami | Miami-Vigilância | RJ | ✅ Ativo | (operando há semanas) |

### Stack técnico

- **Linguagem:** Python 3.12+
- **Fonte de dados:** PNCP API (search + consulta detalhada)
- **Persistência:** JSON local + GitHub Actions Artifacts (90 dias)
- **Notificação:** Telegram Bot API (sendDocument com PDF anexado + caption canônica)
- **Dedup:** arquivos `*_sent.json` por nicho, save incremental a cada 10 envios
- **Concorrência:** lock file por bot, retry 429 com `retry_after`
- **Throttling:** 5s entre envios (~12 msg/min, abaixo do limite Telegram)

### Padrão de formatação canônica (todos os canais)

```
[CABEÇALHO DO CANAL]

📌 Modalidade: ...
🏛 Órgão: ...
🏢 Unidade: ...
📍 UF: ...
🗓 Publicação: dd/mm/aaaa hh:mm
📨 Início propostas: ...
⏰ Fim propostas: ...
🛠 Objeto: ...
💰 Valor: R$ X.XXX,XX | Sigiloso | Não informado
🔗 https://pncp.gov.br/...
```

PDF do edital anexado em cada mensagem (1 GET na API PNCP de arquivos).

### Filtros principais

| Filtro | Onde | Comportamento |
|---|---|---|
| UF | SQL/PNCP search | RJ-only (vigilância, resíduos, aquisição TI) ou SC+RJ (obras) |
| Modalidade | Whitelist por nicho | Cada nicho aceita só as modalidades acessíveis pra empresa-cliente |
| Score keyword | Regex word-boundary | Score ≥ 2 keywords distintas pra obra; matching simples pros outros |
| Exclusões | Lista negra | Veículos, TI/software (no obra), serviços de TI (no aquisição), etc |
| Valor | API detalhada | Aquisição TI: até R$ 80k (faixa ME/EPP exclusivo) |
| Status | API search param | Só `recebendo_proposta` (abertos) |

---

## 🎯 Próximas melhorias

### Imediatas (próxima sessão)

- [ ] **Push do código pro GitHub** + configurar secrets (`TELEGRAM_BOT_TOKEN_OBRA`, `TELEGRAM_CHAT_OBRA`, `TELEGRAM_BOT_TOKEN_AQUISICAO_TI`, `TELEGRAM_CHAT_AQUISICAO_TI`)
- [ ] **Seed inicial dos artifacts** — rodar workflow 1x manualmente upando o sent.json local
- [ ] **Fix falso positivo bot_obra**: adicionar exclusão "aquisição de elevador/lavadora/bomba/equipamento" — caiu 1 falso da Marinha (R$ 16.6k) em manutenção predial RJ
- [ ] **Dashboard simples** — HTML estático mostrando quantos editais por nicho/dia, taxa de envio, falhas

### Curto prazo (1-2 semanas)

- [ ] **Listener Telegram** — botões inline com callback (ex: ⭐ Marcar Pipeline, 📊 Análise IA, ✅ Aprovar)
- [ ] **Integração Trello** — botão "Pipeline" cria card automaticamente no board GB Group
- [ ] **Bot massivo absorvedor** — preenche banco histórico de editais homologados (já existe estrutura, falta rodar)
- [ ] **Métricas básicas** — quantos editais o cliente clicou no PDF (via tracking do botão URL ou evento Telegram)

### Médio prazo (1-3 meses)

- [ ] **Fase 2 do nicho TI** — após 3-5 contratos fechados, ampliar:
  - Modalidades: incluir pregão sem restrição de valor
  - Valor: até R$ 200k inicialmente, depois sem limite
  - CNAEs serviço: ativar busca de desenvolvimento de software, suporte TI, consultoria
- [ ] **Novos nichos** — copeiragem, ASG, motorista, jardinagem, brigada (já mapeado em `project_novos_nichos_abr17.md`)
- [ ] **Análise IA por edital** — botão "Analisar" dispara `agente2_analista` que retorna resumo + pontos de atenção
- [ ] **Geração automática de planilha** — botão "Planilha" gera xlsx IN 05/2017 (já existe `agente3_precificador`)

### Longo prazo (3-6 meses)

- [ ] **SaaS multi-tenant** — onboarding via Telegram, cliente vê só seus editais (deploy Railway)
- [ ] **Backtester contínuo** — calcula acurácia dos filtros vs. editais homologados (`backtester.py` já existe)
- [ ] **Sistema de autoaprendizado** — keywords e exclusões evoluem com base em resultado real (já tem daemon `auto_aprendizado_loop.py` rodando)
- [ ] **App móvel** — wrapper iOS/Android pro Telegram com push otimizado e UX customizada

---

## 🚨 Riscos conhecidos

| Risco | Mitigação atual | Próximo passo |
|---|---|---|
| PNCP API intermitente (timeouts) | Retry 3x com timeout 30s | Cache local de detalhes recentes |
| Edital sem valor no PNCP | Mostra "Não informado", não bloqueia envio | Fallback de soma de itens (já implementado) |
| Falso positivo (ex: "aquisição de elevador" caindo em manutenção) | Score ≥ 2 keywords + lista de exclusões | Refinar exclusões + manual review periódico |
| Telegram rate limit (429) | Retry com `retry_after` + sleep 5s | Aceitável atual |
| 2 instâncias rodando ao mesmo tempo | Lock file com TTL 30min | OK |
| Perda do `*_sent.json` | Backup automático (10 últimos) | Cloud backup adicional |

---

## 🔐 Configuração GitHub Actions (a fazer)

### Secrets necessários (Settings → Secrets and variables → Actions)

| Secret | Valor | Workflow |
|---|---|---|
| `TELEGRAM_BOT_TOKEN_OBRA` | `8766865526:AAFVSM4OBIBCwEV9-JLJhHg-_7GVpeZTuU0` | bot_obra.yml |
| `TELEGRAM_CHAT_OBRA` | `-1003952761388` | bot_obra.yml |
| `TELEGRAM_BOT_TOKEN_AQUISICAO_TI` | `8601601619:AAEdnk7ECbQZqlPONdZw1uYtBxFrXCq_J7Y` | bot_aquisicao_ti.yml |
| `TELEGRAM_CHAT_AQUISICAO_TI` | `-1003989674781` | bot_aquisicao_ti.yml |

### Cron schedules

- **bot_obra.yml**: a cada 2h, 07-19 Brasília, seg-sex (`0 10-23/2 * * 1-5` UTC)
- **bot_aquisicao_ti.yml**: a cada 2h, 07-19 Brasília, seg-sex (`15 10-23/2 * * 1-5` UTC, 15min offset)

---

## 📁 Estrutura de arquivos (resumo)

```
core/skills/
├── bot_obra.py              ← bot consolidado obra/reforma/manutenção predial
├── bot_aquisicao_ti.py      ← bot aquisição TI/eletrônicos
└── ...

empresas/_compartilhado/data/
├── obra_sent.json           ← dedup obra (~233 IDs)
├── aquisicao_ti_sent.json   ← dedup aquisição TI (~33 IDs)
├── backups/                 ← backups automáticos (10 últimos por bot)
└── *.lock                   ← lock files (30min TTL)

.github/workflows/
├── bot_obra.yml             ← agendamento obra
├── bot_aquisicao_ti.yml     ← agendamento aquisição TI
└── pncp_bot.yml             ← bot PNCP standalone (legado)

licitacoes-ai/
├── shared/nichos.py         ← formatar_edital canônico
└── .env                     ← tokens locais (NÃO commitar)
```

---

## ✅ Checklist de produção

- [x] Bot Obra rodando manualmente (233 editais disparados)
- [x] Bot Aquisição TI rodando manualmente (33 editais disparados)
- [x] Workflows GitHub Actions criados localmente
- [x] Padrão de formatação validado pelo cliente
- [x] Dedup persistente testado
- [x] PDF anexado em cada envio
- [x] Lock + retry + backup ativos
- [ ] Push pro GitHub
- [ ] Secrets configurados no GitHub
- [ ] 1ª rodada GitHub Actions executada
- [ ] Monitoramento de falhas (notificar admin se workflow falhar)
