# Octus Chat

Automação de DMs do Instagram no estilo **ManyChat**: conecte uma conta
profissional do Instagram e dispare mensagens automáticas quando alguém
comentar em um post, mandar uma **palavra-chave** na DM ou interagir com um
story.

## Stack

| Camada     | Tecnologia                                         |
| ---------- | -------------------------------------------------- |
| Frontend   | Next.js 15 + React 19 + TypeScript + Tailwind      |
| Backend    | Python + FastAPI (async)                           |
| Banco      | Postgres (Supabase free tier)                      |
| ORM        | SQLAlchemy 2 async + psycopg3 · migrações Alembic  |
| Integração | Meta Graph API (Instagram API with Instagram Login)|
| Deploy     | Frontend → Vercel · Backend → Render (Docker)      |

## Estrutura do backend (em camadas)

```
backend/
├── Dockerfile / Procfile / render.yaml   # deploy (roda as migrações no boot)
├── requirements.txt / requirements-dev.txt
├── alembic.ini + alembic/versions/       # migrações do schema
├── scripts/
│   ├── check_schema.py                   # compara banco × models (só leitura)
│   └── rotate_token_key.py               # recifra tokens com a chave nova
├── tests/                                # pytest
└── app/
    ├── main.py                 # entrypoint + lifespan (sobe o worker)
    ├── core/
    │   ├── config.py           # settings via .env (pydantic-settings)
    │   ├── database.py         # engine async + Base + get_session
    │   ├── auth.py             # segredo da API + state do OAuth
    │   ├── crypto.py           # Fernet dos tokens da Meta
    │   └── security.py         # assinatura do webhook + remoção de segredos
    ├── models/                 # ORM (contas, automações, contatos, mensagens,
    │                           #      message_logs, webhook_events)
    ├── schemas/                # contratos da API (Pydantic)
    ├── crud/                   # acesso a dados isolado
    ├── services/
    │   ├── instagram_api.py    # cliente da Graph API (token no header)
    │   ├── token_service.py    # único lugar que cifra/decifra o token
    │   ├── automation_engine.py# regra: evento → automação → DMs
    │   ├── flow_runner.py      # flow em grafo (mensagens + condições)
    │   ├── webhook_events.py   # corpo do webhook → eventos da fila
    │   └── send_limiter.py     # ponto de extensão p/ rate limit por conta
    ├── workers/
    │   └── webhook_worker.py   # consome a fila (SKIP LOCKED)
    └── routers/
        ├── health.py
        ├── webhooks.py         # webhook da Meta: enfileira e responde 200
        ├── instagram.py        # OAuth connect/callback + diagnóstico
        ├── automations.py      # CRUD de automações
        ├── contacts.py
        └── conversations.py
```

**Fluxo principal:** a Meta chama `POST /webhooks/instagram` → o endpoint
valida a assinatura, grava cada comentário/mensagem em `webhook_events`
(reenvios são descartados pela `dedupe_key`) e responde **200 na hora** → o
worker pega os eventos com `SELECT … FOR UPDATE SKIP LOCKED` e chama o
`automation_engine`, que encontra a automação, envia a DM (e o flow) e
registra em `message_logs` (evita responder 2x).

### Segurança

- **Login:** por e-mail e senha (usuários na tabela `users`, senha com scrypt).
  Quem valida é o backend (`POST /auth/login`); o Next grava um cookie httpOnly
  `<uid>.<exp>.<hmac>`, assinado com `SESSION_SECRET`. Cada usuário vê só as
  contas do Instagram que são dele (`instagram_accounts.owner_user_id`).
- **API:** o browser nunca fala direto com o backend. O route handler
  `frontend/app/api/backend/[...path]` confere a sessão e injeta, server-side,
  `X-Octus-Secret` e `X-Octus-User` (o usuário da sessão; um `X-Octus-User`
  vindo do browser é ignorado). O backend recusa qualquer chamada sem o
  segredo e sem um usuário válido, exceto `/health`, o webhook da Meta
  (verificado pela assinatura) e o callback do OAuth (verificado pelo `state`
  assinado, que carrega o id de quem iniciou a conexão). Conta de outro
  usuário responde **404**, igual a uma conta que não existe.
- **Tokens da Meta:** cifrados no banco (Fernet, `TOKEN_ENCRYPTION_KEYS`),
  enviados no header `Authorization` e removidos de logs e mensagens de erro.

## Variáveis de ambiente

### Backend (`backend/.env` em dev · painel do Render em produção)

| Variável | Obrigatória | Para quê |
| --- | --- | --- |
| `DATABASE_URL` | sim | Postgres do app. No Supabase: *Transaction pooler* (porta 6543), prefixo `postgresql+psycopg://` |
| `MIGRATIONS_DATABASE_URL` | não | URL só para as migrações. No Supabase: *Session pooler* (porta 5432). Vazio = usa `DATABASE_URL` |
| `API_SECRET` | sim | Segredo compartilhado com o proxy do frontend. Vazio = API recusa tudo |
| `TOKEN_ENCRYPTION_KEYS` | sim | Chave(s) Fernet dos tokens, separadas por vírgula (a 1ª cifra). **Perder a chave = reconectar o Instagram** |
| `META_APP_ID` / `META_APP_SECRET` | sim | App da Meta (o secret também valida o webhook) |
| `WEBHOOK_VERIFY_TOKEN` | sim | Token que você repete no painel da Meta |
| `OAUTH_REDIRECT_URI` | sim | `https://SEU_BACKEND/instagram/callback` |
| `FRONTEND_URL` | sim | Para onde o OAuth volta (ex.: `https://seu-app.vercel.app`) |
| `ENVIRONMENT` | não | `production` desliga `/docs` |
| `WEBHOOK_WORKER_ENABLED` | não | `true` (padrão) roda o worker dentro do servidor web |
| `GRAPH_API_VERSION` / `DB_ECHO` | não | `v21.0` / `false` |

### Frontend (`frontend/.env.local` em dev · painel da Vercel em produção)

| Variável | Para quê |
| --- | --- |
| `BACKEND_URL` | URL do backend (ex.: `https://seu-backend.onrender.com`) |
| `SESSION_SECRET` | Assina o cookie de sessão (trocar = desloga todo mundo) |
| `BACKEND_API_SECRET` | **Mesmo valor** de `API_SECRET` do backend |

Gerar os segredos:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"   # API_SECRET, SESSION_SECRET
backend/.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # TOKEN_ENCRYPTION_KEYS
```

## Banco de dados — Supabase (free)

1. Crie um projeto em https://supabase.com (free tier).
2. Clique em **Connect** e copie as strings do **Transaction pooler** (porta
   6543, para `DATABASE_URL`) e do **Session pooler** (porta 5432, para
   `MIGRATIONS_DATABASE_URL`). Troque o prefixo `postgresql://` por
   `postgresql+psycopg://`. Caracteres especiais na senha precisam ser
   codificados (`@` → `%40`, `,` → `%2C`…).
3. Trocar a senha do banco: **Database → Settings → Reset database password**
   (lembre de atualizar o `DATABASE_URL` do Render na sequência).

> O free tier pausa o projeto após ~1 semana de inatividade (reativa com 1 clique).

## Rodar local

### Backend

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env               # preencher (ver tabela acima)
.venv/bin/alembic upgrade head     # cria/atualiza as tabelas
.venv/bin/uvicorn app.main:app --reload   # http://localhost:8000 (docs em /docs)
```

> No Windows, use `.venv\Scripts\...` e `python run.py` no lugar do uvicorn
> (o psycopg async precisa do SelectorEventLoop).

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local         # BACKEND_URL, SESSION_SECRET, BACKEND_API_SECRET
npm run dev                        # http://localhost:3000 → tela de login (crie um usuário antes: ver "Usuários e testadores")
```

## Usuários e testadores

Não há cadastro pela tela: quem administra cria o usuário por linha de comando
(a partir de `backend/`, com o `.env` do ambiente alvo):

```bash
# o dono: admin, e fica com as contas do Instagram que ainda não têm dono
python -m scripts.create_user --email dono@x.com --name "Arthur" --admin --claim-orphans
# um testador
python -m scripts.create_user --email testador@x.com --name "Fulano"
# esqueceu a senha: gera outra temporária
python -m scripts.create_user --email testador@x.com --reset-password
```

O script imprime uma **senha temporária, uma única vez** (mande por um canal
privado). No primeiro acesso a pessoa é levada a trocá-la (mínimo de 10
caracteres). `--claim-orphans` só vale com `--admin`; se houver contas sem dono
e a flag não vier, o script avisa. A migração 0005 não cria usuário: depois de
subir a versão com multiusuário, rode o comando do dono.

### Como adicionar um testador

Na ordem, **depois** do deploy:

1. **Meta App** (developers.facebook.com → o app → *App roles* → *Roles*):
   adicione a pessoa como **Instagram Tester** pelo @ do Instagram dela. Com o
   app em modo de desenvolvimento, sem esse papel a Meta recusa o OAuth e não
   entrega os webhooks da conta.
2. **A pessoa**, no Instagram:
   - a conta precisa ser **profissional** (Criador ou Empresa);
   - aceitar o convite em *Configurações → Apps e sites → Convites de testador*
     (no navegador: instagram.com/accounts/manage_access);
   - em *Configurações → Mensagens → Ferramentas conectadas*, ativar **Permitir
     acesso às mensagens** (sem isso, as DMs pela API falham).
3. **Crie o usuário** dela com `scripts.create_user` (acima) e envie a senha temporária.
4. Ela entra em `/login`, troca a senha, vai em **Configurações → Conectar
   Instagram** e cria uma automação de teste (ex.: comentário com a palavra-chave
   `TESTE` num post dela).

### Saúde do token da Meta

A Meta invalida o token se a conta ficar parada por ~60 dias. O backend marca a
conta (`token_invalid_at`) quando a Meta responde com o código 190, e a tela
mostra "Reconectar" (banner no Início, ponto vermelho no seletor de conta).
O worker também renova, a cada ~12 h, os tokens que vencem em até 15 dias.

## Migrações (Alembic)

O schema é gerido só pelo Alembic — o app **não** cria tabelas sozinho. Em
produção, o container roda `alembic upgrade head` antes de subir.

```bash
cd backend
.venv/bin/alembic upgrade head                          # aplica as pendentes
.venv/bin/alembic current                               # versão do banco
.venv/bin/alembic revision --autogenerate -m "descricao" # nova migração (revise o arquivo!)
.venv/bin/alembic downgrade -1                          # desfaz a última
.venv/bin/python -m scripts.check_schema                # banco × models, só leitura
```

| Revisão | O que faz |
| --- | --- |
| `0001` | Baseline do schema que já existia (o Supabase foi marcado com `alembic stamp 0001`) |
| `0002` | Cifra os tokens: `access_token` → `access_token_enc` (exige `TOKEN_ENCRYPTION_KEYS`) |
| `0003` | Cria a fila `webhook_events` |

**Banco que já existia sem Alembic:** rode `check_schema` e, se conferir,
`alembic stamp 0001` (não rode `upgrade` na baseline).

**Rotação da chave dos tokens:** coloque a chave nova na frente
(`TOKEN_ENCRYPTION_KEYS=nova,antiga`), faça deploy, rode
`python -m scripts.rotate_token_key` e depois remova a antiga.

## Testes

```bash
cd backend
.venv/bin/pytest
```

Os testes de unidade (flow, assinatura, auth, criptografia, cliente da Meta
sem rede) rodam sem banco. Os que usam banco (fila de webhooks, usuários,
rotas por dono, engine, migrações) precisam de um Postgres **descartável** (o
schema é recriado a cada teste) e são pulados sem ele. **Nunca aponte
`TEST_DATABASE_URL` para o Supabase.** Com podman:

```bash
podman run -d --rm --name octus-test-pg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=octus_test \
  -p 127.0.0.1:55432:5432 docker.io/library/postgres:17-alpine
TEST_DATABASE_URL=postgresql+psycopg://postgres:test@127.0.0.1:55432/octus_test .venv/bin/pytest
```

## Worker da fila de webhooks

Roda como task asyncio dentro do servidor web (lifespan), sem Redis:
acorda na hora quando chega um webhook e, ocioso, consulta a fila a cada 2 s.
Falhas são tentadas de novo (30 s, 2 min) e, na 3ª, o evento fica `failed`
em `webhook_events` para inspeção. Eventos presos em `processing` voltam à
fila após 5 min; os `done` são apagados após 14 dias.

Para rodar como processo separado no futuro: `python -m app.workers.webhook_worker`
e `WEBHOOK_WORKER_ENABLED=false` no serviço web.

## Deploy

- **Frontend → Vercel:** root `frontend/`, variáveis da tabela do frontend.
- **Backend → Render:** usa o `Dockerfile` (o `render.yaml` lista as
  variáveis). Deploy automático a cada push na `main`.
- **Multiusuário (migração 0005):** o backend novo exige `X-Octus-User` e o
  frontend antigo não manda, então **suba os dois juntos** (merge na `main`). O
  Render roda `alembic upgrade head`. Assim que terminar, rode
  `create_user --admin --claim-orphans` contra o banco de produção (cria o seu
  usuário e passa as contas existentes para você) e remova `ADMIN_PASSWORD` da
  Vercel. Enquanto isso não for feito, ninguém consegue entrar.
- **Ordem ao adicionar variável obrigatória nova:** configure no painel
  **antes** do push — senão a migração/boot falha (o Postgres desfaz a
  migração e o deploy anterior continua no ar).
- O plano free do Render dorme após ~15 min sem tráfego; o próprio webhook o
  acorda (a Meta reenvia se estourar o timeout, e a dedupe evita duplicar).

## Configuração da Meta

1. Crie um app em https://developers.facebook.com/apps e adicione **Instagram**.
2. Webhook → `https://SEU_BACKEND/webhooks/instagram` com o `WEBHOOK_VERIFY_TOKEN`.
3. Assine os campos **comments** e **messages**.
4. Conecte a conta pelo painel: **Configurações → Conectar Instagram**.
5. Em dev, exponha o backend local com ngrok/cloudflared (a Meta exige HTTPS).
