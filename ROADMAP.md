# 🗺️ ROADMAP — InboxPilot rumo à paridade com o ManyChat

> Mapeamento completo do ManyChat (docs oficiais + reviews 2026) comparado ao
> estado atual do InboxPilot. Meta: **réplica funcional focada em Instagram**.
> Atualizado: 2026-07-02

---

## 1. Modelo conceitual do ManyChat

```
GATILHO (trigger) ──► FLOW (automação visual) ──► CONTATO atualizado
   │                     │
   │                     ├── Mensagens (blocos de conteúdo ricos)
   │                     ├── Condições (if/else por tag/campo/segmento)
   │                     ├── Ações (tag, campo, sequência, webhook, notificar)
   │                     ├── Smart Delay (tempo/data, janela de horário)
   │                     ├── Randomizador (teste A/B)
   │                     └── AI Step (conversa guiada por objetivo)
   │
CONTATOS (CRM): tags, campos custom, segmentos, opt-in por canal
SEQUÊNCIAS (drip) · BROADCASTS (massa) · INBOX (live chat + human takeover)
ANALYTICS · GROWTH TOOLS (ref links/QR/widgets) · INTEGRAÇÕES · IA
```

---

## 2. Inventário de funções × status no InboxPilot

### 2.1 Canais
| Função ManyChat | Status | Nota |
|---|---|---|
| Instagram | 🟢 | nosso único canal (foco do projeto) |
| Messenger / WhatsApp / SMS / Email / TikTok / Telegram | ⬜ fora do escopo | exigem outras APIs/contratos (BSP, Twilio…) |

### 2.2 Gatilhos (Instagram)
| Função | Status | Falta |
|---|---|---|
| Comentário em post/reel (palavra-chave ou qualquer) | 🟢 | — |
| Escopo: post específico / todos / **próxima publicação** | 🟢 | `bind_next` + baseline de mídias |
| **Resposta pública ao comentário** ("Enviei no seu direct 🚀") | 🟢 | `public_reply` → POST `/{comment}/replies` |
| Exclusão de palavras (negative keywords) | 🟢 | `exclude_keywords` no `find_matching` |
| **Palavra-chave em DM** (Keywords trigger) | 🟢 | `dm_keyword` → `find_matching_dm` no webhook `messages` |
| **Story Reply** (resposta/reação a story, c/ keywords) | 🟢 | `story_reply` (keyword opcional) → `find_matching_story` via `reply_to.story` |
| **Story Mention** (mencionaram a conta no story) | 🟢 | `story_mention` → `find_matching_story_mention` via attachment `story_mention` |
| Live comments | ❌ | campo `live_comments` |
| Default Reply (fallback p/ qualquer DM sem match) | 🟢 | `dm_any` (fallback no `find_matching_dm`) |
| Welcome / Conversation starters (ice breakers) | ❌ | API de ice breakers |
| Ref URL (ig.me) / QR code | ❌ | gerar links + parse de ref |
| AI Intents (gatilho por intenção, não keyword) | ❌ | LLM (fase IA) |

### 2.3 Builder / Flow
| Função | Status | Falta |
|---|---|---|
| Quick Automation (form guiado simples) | 🟢 | é o nosso builder atual |
| **Flow Builder visual (canvas, nós arrastáveis)** | 🟢 | React Flow: gatilho→mensagens conectados, edição inline, add/remover e **arrastar p/ reordenar** |
| Multi-mensagem em sequência num flow | 🟢 | coluna `flow` (passos extras) + `_send_followups` no engine |
| Condição (if/else) | 🟡 | engine pronto (`flow_runner`: grafo + ramos sim/não). Falta o nó no canvas |
| Ações (tag, campo, notificar, webhook externo) | ❌ | engine + CRM |
| Smart Delay (duração/data + janela de horário) | ❌ | scheduler/worker |
| Randomizador (A/B) | ❌ | engine |
| Rascunho vs publicado | ❌ | campo `status` |
| Pastas de automações | ❌ | organização |
| Flow Builder AI (gera flow por prompt) | ❌ | fase IA |

### 2.4 Conteúdo das mensagens (blocos IG)
| Função | Status | Falta |
|---|---|---|
| Texto | 🟢 | — |
| Texto + link embutido | 🟢 | nosso texto+link atual |
| **Botões de link (até 3, web_url)** | 🟢 | `buttons` → button template (fallback p/ private reply) |
| Botões postback (continuar flow) | ⬜ | depende do engine (Fase 3) |
| **Quick Replies (até 12)** | ❌ | payload `quick_replies` (Fase 3) |
| Imagem / Áudio / Vídeo / Arquivo | ❌ | attachment payloads |
| Card (imagem + botões) / Galeria (até 10) | ❌ | `generic` template |
| Coleta de dados (pergunta → salva em campo) | ❌ | engine + campos custom |
| Variáveis na mensagem ({{first_name}} etc.) | ❌ | templating simples |

### 2.5 Contatos (CRM)
| Função | Status | Falta |
|---|---|---|
| Captura automática (comentou/DM → contato) | 🟢 | — |
| @username + foto | 🟢 | best-effort via API |
| **Tags** | ❌ | tabela + UI + ações |
| **Campos personalizados** (+ sistema: nome, idioma…) | ❌ | tabela + UI |
| **Segmentos** (filtros salvos) | ❌ | filtros + persistência |
| Busca/filtro na lista | ❌ | UI |
| Import/export, ações em massa | ❌ | CSV + bulk |
| Opt-in/opt-out por canal | ❌ | compliance |

### 2.6 Sequências e Broadcasts
| Função | Status | Falta |
|---|---|---|
| **Sequências (drip)** com delays | ❌ | scheduler/worker + UI |
| **Broadcast real** p/ segmento | 🟡 esqueleto | envio + janela 24h + fila |
| Agendamento de broadcast | ❌ | scheduler |
| Stats de broadcast (enviado/aberto/clicado) | ❌ | tracking |

### 2.7 Inbox (Live Chat)
| Função | Status | Falta |
|---|---|---|
| Histórico de conversas (in/out) | 🟢 | — |
| **Enviar mensagem manual (human takeover)** | ❌ | POST send + janela 24h |
| Pausar automação por conversa | ❌ | flag no contato |
| Tempo real (novas msgs sem F5) | ❌ | polling/SSE |
| Atribuição a agentes / notas / status aberto-resolvido | ❌ | multiusuário (futuro) |

### 2.8 IA (add-on do ManyChat, US$ 29/mês)
| Função | Status | Falta |
|---|---|---|
| AI Step (conversa com objetivo/contexto) | ❌ | Claude API 😉 |
| AI Intents | ❌ | classificação de intenção |
| Text Improver / Flow Assistant | ❌ | fase IA |

### 2.9 Analytics / Growth / Integrações / Plataforma
| Função | Status | Falta |
|---|---|---|
| Dashboard (contatos, execuções, CTR, open rate) | ❌ | tracking de eventos + UI |
| Stats por automação (runs, CTR) | 🟡 | temos `message_logs`; falta agregar/expor |
| Ref URLs / QR / widgets de site | ❌ | growth tools |
| Templates (marketplace) | ⬜ | ecossistema, não prioridade |
| Integrações (Sheets, Shopify, Zapier, webhooks out) | ❌ | External Request primeiro |
| API pública | ❌ | futuro |
| Multiusuário/equipe + login | ❌ | app é single-user hoje (1-3 pessoas) |

---

## 3. ⚠️ O que NÃO dá pra copiar 1:1 (restrições de plataforma)
1. **Multicanal completo** (WhatsApp/SMS/Email/TikTok) — outras APIs, contratos e custos. Decisão: fora do escopo; foco IG.
2. **Qualquer conta conectar** — exige **App Review da Meta** (advanced access). Hoje: só contas testadoras do app.
3. **Janela de 24h da Meta** — broadcasts/sequências só alcançam quem interagiu nas últimas 24h (o ManyChat vive sob a mesma regra).
4. **Ecossistema** (marketplace de templates, agências, cursos) — não é código.

---

## 4. Fases de implementação (ordem recomendada)

### Fase 1 — Fechar o caso de uso nº 1 (comment-to-DM completo) ✅ CONCLUÍDA
O combo mais usado do ManyChat: comentário → **resposta pública** + DM com **botão** → clique abre janela 24h → follow-up com link.
- [x] Resposta pública automática ao comentário (`public_reply`)
- [x] Exclusão de palavras-chave (`exclude_keywords`)
- [x] Botões de link na DM (até 3, button template + fallback) ← falta confirmar ao vivo
- [x] "Próxima publicação" (`bind_next` + baseline de mídias)
- [x] Retry/backoff nos envios (`_post` em instagram_api)
- [ ] Quick Replies (chips) — junto do engine de flow (Fase 3)
- [ ] Fila real/worker (só se escalar; hoje retry inline basta p/ 1-3 pessoas)

### Fase 2 — Novos gatilhos ✅ CONCLUÍDA (por partes testáveis)
- [x] **Parte 1:** Palavra-chave em DM (`dm_keyword`) + Default Reply (`dm_any`)
- [x] **Parte 2:** Story Reply (`story_reply`, keyword opcional) — via `reply_to.story` no webhook
- [x] **Parte 3:** Story Mention (`story_mention`) — via attachment `story_mention` no webhook
- [ ] **Parte 4 (opc):** Ice breakers · Ref links (ig.me)

### Fase 3 — Flow Builder visual + engine multi-step ⬅ EM ANDAMENTO (por partes testáveis)
- [x] **Parte 1:** Mensagens em sequência (coluna `flow` + `_send_followups`) + repetidor no builder + preview empilhado
- [x] **Parte 2:** Canvas visual (React Flow) sobre o modelo `flow` — gatilho→mensagens, edição inline, add/remover
- [x] **Parte 2.1:** arrastar nós para reordenar a sequência (ids estáveis por mensagem)
- [x] **Parte 3.1:** Engine de grafo (`flow_runner`) + nós de Condição (if/else) — backend, retrocompatível
- [ ] **Parte 3.2:** Nó de Condição no canvas (saídas Sim/Não)
- [ ] **Parte 3.3:** Quick Replies + postback (retoma o flow no clique — exige estado de execução)
- [ ] **Parte 3.4:** Smart Delay (worker/scheduler)
- [ ] **Parte 4:** Rascunho vs publicado · Randomizador (A/B)

### Fase 4 — CRM completo
- [ ] Tags · [ ] Campos custom · [ ] Segmentos · [ ] Sequências (scheduler) · [ ] Broadcast real

### Fase 5 — Inbox vivo
- [ ] Enviar manual · [ ] Pausar automação · [ ] Tempo real (polling/SSE)

### Fase 6 — IA
- [ ] AI Step (Claude API) · [ ] Intents · [ ] Gerador de flows

### Fase 7 — Plataforma
- [ ] Analytics · [ ] Growth tools · [ ] App Review da Meta · [ ] Login/equipe · [ ] Integrações

---

## 5. Fontes
- https://help.manychat.com/hc/en-us/articles/14281316989724 (Comments trigger)
- https://help.manychat.com/hc/en-us/articles/14281211785884 (Keywords trigger)
- https://help.manychat.com/hc/en-us/articles/14281309502108 (Story Mention)
- https://help.manychat.com/hc/en-us/articles/13556930006428 (Story Reply)
- https://help.manychat.com/hc/en-us/articles/14281196200604 (Content Block types)
- https://help.manychat.com/hc/en-us/articles/14281157129116 (Quick Replies)
- https://help.manychat.com/hc/en-us/articles/14281157003292 (Buttons)
- https://help.manychat.com/hc/en-us/articles/14281197046812 (Smart Delay)
- https://help.manychat.com/hc/en-us/articles/14281110746012 (Contacts)
- https://help.manychat.com/hc/en-us/articles/14281070478748 (Inbox)
- https://help.manychat.com/hc/en-us/articles/14281187288860 (AI Step)
- https://manychat.com/product/instagram · reviews 2026 (flowgent.ai, setsmart.io, chatimize.com)
