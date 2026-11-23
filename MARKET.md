# 📊 Mercado — Dores do ManyChat & Diferenciais do Octus Chat

> Varredura de reviews, Reddit/Trustpilot/BBB e comparativos de concorrentes (2026).
> Objetivo: entender por que as pessoas reclamam do ManyChat e onde o Octus Chat
> pode ser um diferencial real. Atualizado: 2026-07-02.

---

## 1. As maiores dores do ManyChat (2026)

| # | Dor | Detalhe |
|---|-----|---------|
| 1 | **Preço por contato que escala** | Cobra por nº de contatos — a conta cresce junto com o público, mesmo sem mais engajamento. Relatos de **contas 2–3× maiores** de repente. É a **reclamação nº 1**. |
| 2 | **Free plan esvaziado** | Em **mar/2026** o plano grátis caiu de **1.000 → 25 contatos**. Sensação de "isca e troca". |
| 3 | **Cobrança & suporte** | Cobranças **após cancelar**, dificuldade de reembolso; suporte **só por e-mail** e lento; **nota F no BBB** por não responder reclamações. |
| 4 | **IA fraca pelo preço** | O "AI Step" (US$ 29/mês) é mais **keyword matching** do que IA de verdade: não aprende com seu conteúdo nem mantém contexto. |
| 5 | **Complexidade multicanal** | Plataforma "Facebook-first"; quem só usa **Instagram** paga por complexidade que não usa. |

## 2. O que os usuários DESEJAM (e por que trocam)

- **Preço fixo e previsível** (flat), sem tarifa por contato
- **Contatos ilimitados**
- **Foco em Instagram** (não Facebook-first), simples e rápido
- **Comment → DM** veloz e confiável
- **Setup rápido com preview visual**
- Concorrentes que crescem com isso: InstantDM (~US$9), CreatorFlow (US$15 flat),
  LinkDM (US$19 flat), DMdaddy (~US$9) — todos **flat + IG-first + simples**.

---

## 3. 🚀 Onde o Octus Chat pode ser diferencial

### 3.1 O trunfo: **self-hosted = sem cobrança por contato**
O Octus Chat roda na **sua própria infra** (Supabase + Render). Isso ataca de frente
a dor nº 1 e nº 2 do ManyChat:
- **Contatos ilimitados** por design (é o *seu* banco).
- **Custo fixo e baixíssimo** (free tiers p/ escala pequena; sem tarifa por contato).
- **Sem armadilha de cobrança / cancelamento** — não há fatura recorrente de SaaS.
- **Você é dono dos dados** (privacidade, sem lock-in).

> Posicionamento sugerido: **"O ManyChat que você hospeda: contatos ilimitados,
> foco no Instagram, sem cobrança por contato e com IA de verdade."**

### 3.2 Foco em Instagram + simplicidade (já temos)
- IG-first, UI limpa, **preview ao vivo** (agora num iPhone) — exatamente o que
  os desertores do ManyChat pedem. Manter essa vantagem.

### 3.3 IA de verdade (wedge da Fase 6)
- A IA do ManyChat decepciona. Plugar **Claude** (contexto real, responde de
  verdade, recomenda produtos) seria um **diferencial forte** — não keyword matching.

### 3.4 Transparência de custo/uso
- Uma telinha de "uso" (contatos, DMs enviadas, custo estimado da infra) reforça a
  narrativa "sem surpresa na fatura".

---

## 4. ⚠️ Trade-offs honestos (o outro lado)
- **Self-hosted tem fricção de setup** (Meta App Review, deploy). Mitigação: nós já
  automatizamos boa parte; um "setup guiado" seria ouro para vender isso.
- **Sem multicanal** (WhatsApp/SMS) — mas a pesquisa mostra que IG-only é *feature*,
  não bug, para o público-alvo (criadores/pequenos negócios de Instagram).
- **App Review da Meta** é obrigatório para abrir ao público (burocracia, não código).

---

## 5. Implicações para o roadmap
1. **Manter simplicidade + preview** como marca (feito: iPhone preview).
2. Priorizar a **IA com Claude** (Fase 6) como diferencial competitivo, não só "mais um item".
3. Considerar **tela de uso/custo** (transparência) — barato e alinhado ao posicionamento.
4. Se um dia virar produto para terceiros: um **setup guiado** (conectar Meta, deploy)
   transforma a fricção do self-hosted em vantagem ("seu ManyChat, sua infra").

## 6. Fontes
- https://flowgent.ai/blog/manychat-review · https://flowgent.ai/blog/manychat-pricing
- https://creatorflow.so/blog/manychat-pricing-trap/ · https://setsmart.io/blog/manychat-pricing
- https://hackceleration.com/labs/review/manychat · https://superpower.social/blogs/is-manychat-really-free-2026
- https://instantdm.com/blog/top-15-manychat-alternatives-for-instagram-automation-in-2026
- https://creatorflow.so/blog/manychat-alternatives-instagram/ · https://creatorflow.so/vs/manychat
- https://instantdm.com/vs/manychat/ · https://www.inro.social/blog/manychat-competitors-alternatives-2026

---

## 7. Rodada 2 — nome, diferenciais de features, técnicos e de onboarding (2026-11-23)

> Pesquisa por 4 agentes em paralelo. Fontes majoritariamente de fóruns, reviews e
> blogs de concorrentes (não é pesquisa formal). Itens marcados **[não verificado]**
> precisam de checagem na fonte oficial antes de entrar em marketing.

### 7.1 Nome do produto

"Octus Chat" foi considerado fraco. Candidatos com melhor racional:

| Nome | Racional | Conflito encontrado | Situação |
|------|----------|---------------------|----------|
| **Sparkdm** | "DM" deixa o produto claro para quem busca no Instagram | Nenhum produto de DM com esse nome; "Spark" é radical muito usado | Livre na busca; **marca não verificada** |
| **Triggra** | Inventado, curto, pronunciável em PT e EN; "trigger" = gatilho | Nenhum match de produto | Livre na busca; **marca não verificada** |
| **Gatilho** | Forte em PT; "gatilho de comentário" é a ideia do produto | Nenhum software encontrado | Palavra genérica: difícil de registrar; só faz sentido se o foco for Brasil |

Evitar: **Echora** (marca ativa nos EUA), **Replio** (produtos similares), **Hookly** (app de crochê na App Store — setor diferente, mas mesmo nome).

- **Não confirmado:** domínios (.com/.io/.app) e registros em INPI/USPTO. Antes de escolher: buscar nas classes 9, 35, 42 e 45 no INPI e no USPTO, e validar com advogado de PI.

### 7.2 Diferenciais de features (o que concorrentes fazem mal)

Prioridade por **custo baixo + queixa clara de concorrente**:

1. **Entrega transparente por comentário** (baixo) — mostrar se a resposta pública e a DM saíram e, se não, o motivo. ManyChat tem relatos de 350 respostas públicas e só 77 DMs, sem explicação.
2. **Saúde das automações com alerta** (baixo) — status do webhook, última entrega, falhas, aviso quando um gatilho para de disparar. Queixa recorrente no Trustpilot do ManyChat (nota ~2,1–2,2).
3. **Webhooks de saída com fila, retry e replay** (baixo, a fila já existe) — o bloco External Request do ManyChat espera ~10 s e não tem PATCH.
4. **Janela de 24h visível e à prova de erro** (baixo, a 3.3a já tem a janela) — contador por contato e bloqueio com explicação.
5. **Histórico de métricas por automação** (médio) — ManyChat mostra só totais acumulados.
6. **Variações de mensagem com A/B até conversão real** (médio) — ManyChat limita a 3 variações e mede só até a conclusão do fluxo.
7. **Moderação de comentários no gatilho** (médio) — ocultar spam/ofensas com lista editável. Não achei recurso nativo confirmado no ManyChat. **[não verificado]** endpoint de ocultar comentário na Graph API.
8. **IA que admite não saber e escala para humano** (alto, depende da Fase 6) — responde só com base no catálogo/políticas; recusa e escala quando não cobre.
9. **Ritmo de envio conservador** (médio) — espaçar DMs e avisar antes do limite de risco. Evidência fraca.
- Captura de lead com validação de e-mail/telefone: **sem fonte** de queixa; não recomendo como diferencial sem pesquisa própria.

### 7.3 Diferenciais técnicos e de confiança (self-hosted)

1. **Licença declarada** (baixo) — o OpenReply (MIT) já existe, então a licença sozinha não diferencia. AGPL pode proteger contra clone SaaS **[não verificado]**.
2. **`docker compose up` em um comando** (médio) — LibreChat e Typebot vendem isso. O wizard de env e as migrações já existem.
3. **Exportação de dados e docs de LGPD** (baixo–médio) — mapa de dados, retenção (janela de 24h já existe), exportação CSV/JSON. Self-hosted não torna nada compliant sozinho; ajudar o dono a cumprir é diferencial real.
4. **Alerta de política da Meta na UI** (médio) — mostrar o caminho de handoff humano e o risco da Human Agent tag. É o diferencial mais específico do nicho.
5. **BYOK** (médio) — chave de IA própria; ligado ao plano de IA com Claude, o dono controla custo e modelo.
6. **Lançamento com comunidade** (baixo) — Show HN, r/selfhosted, README com GIF. Números de stars citados são de casos pontuais.
- **Open-source concorrentes diretos:** OpenReply (MIT, github.com/diwenne/openreply), InstaAuto, Pilot (github.com/getpilot/app), Nudgra, BrightBean Chat, Zernflow. Licença e stars **[não verificadas]** na maioria — conferir nos repositórios antes de comparar publicamente.
- Mercado "manychat-alternative" no GitHub é pequeno e pouco disputado (~113 stars em 8 repos, número aproximado).

### 7.4 Posicionamento e onboarding

1. **Setup guiado com diagnóstico de conta profissional** (alto impacto, médio) — a maior fonte de desistência nos fóruns do ManyChat ("account might not support this method yet").
2. **Checklist de App Review com roteiro de gravação** (alto, médio) — a Meta exige gravação de tela com DM real recebida e respondida. Motivos de rejeição de terceiros **não são oficiais**.
3. **Pausa automática quando um humano responde** + retomar com um clique (alto, baixo–médio) — pedido recorrente da comunidade.
4. **"Humano assume" com escalonamento** (alto) — a Meta exige caminho de escalonamento para humano (página oficial verificada).
5. **Log "por que o bot respondeu"** (médio) — transparência e diagnóstico.
6. **Simulação com dados reais antes de publicar** (médio) — não achei concorrente que faça isso comprovadamente; pode ser diferencial real.
7. **"Saúde da conta" e rampa de volume** (alto para o eixo "seguro") — não há limite oficial confirmado.

**Slogans sugeridos (a validar):**
- "Contatos ilimitados. Sem surpresa na fatura."
- "Seu Instagram vendendo sozinho, na sua infra."
- "Automação de Instagram que você controla."
- "Conecte, teste, publique."
- "Automatiza, e o humano assume quando precisar."

### 7.5 Alertas de dado (não usar em marketing sem checar)

- **Janela de 24h:** a política oficial da Meta diz 24h. Fonte secundária fala de 7 dias para anúncios Click-to-Messenger desde 28/09/2026 — **[não confirmado]** na documentação oficial.
- **Banimento por automação:** relatos de fórum, não confirmados pela Meta. Não há prova de que a ferramenta causa banimento em si.
- **Números de limite de envio, "zero ban" e stars de concorrentes:** não verificados.

### 7.6 Próximos passos sugeridos

1. Checar Sparkdm e Triggra no INPI/USPTO e domínios; escolher entre eles e Gatilho (se o foco for Brasil).
2. Confirmar a janela de 7 dias para anúncios na documentação oficial da Meta.
3. Priorizar os diferenciais baratos que já se apoiam na fila e no envio central: **7.2 itens 1, 2, 3 e 4** e **7.3 item 3** (LGPD/exportação).
4. Decidir licença (MIT vs AGPL) antes de qualquer divulgação pública.

### 7.7 Gate de marca — Triggra (2026-11-23) — **NÃO PASSOU**

Checagem por busca web (sem acesso direto às bases oficiais). Resultado: **não é possível afirmar que Triggra está livre.**

- **INPI (classes 9, 35, 42):** não consultado diretamente (busca.inpi.gov.br não acessível pela busca web). Nada encontrado para "Triggra".
- **USPTO / EUIPO:** nada para "Triggra". Marcas próximas com software na mesma área:
  - **TRIGGRE** (Triggre Intellectual Property B.V., depositada 2023-01-11, software e produtos de computador) — colisão fonética direta.
  - **TRIGGAR** (Postcode Anywhere (Europe) Ltd., depositada 2015-07-14, software) — mais distante, mas na mesma classe.
- **Software com nome parecido:** Triggr (ferramenta de notificação para vendas, Austrália), trigr (G2/Capterra), TriggerApp (gestão de projetos), Trigger.io (framework mobile). Não são o mesmo nome, mas são de software e disputam a mesma palavra.
- **Domínios** (triggra.com, .com.br, .io, .app): sem registro DNS, mas sem `whois` no ambiente, então **não confirmado**. Nenhuma listagem de venda encontrada.
- **Handles** (Instagram, GitHub, TikTok): nenhum perfil com o nome exato. **Checagem superficial** (uma busca).

**Decisão:** Triggra fica **bloqueado** até um advogado de PI ou o próprio dono consultar INPI e USPTO/EUIPO diretamente. TRIGGRE é a colisão mais séria. Fallback do plano (Sparkdm) ainda precisa do mesmo gate.
