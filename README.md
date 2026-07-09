# Octus Chat

Automação de DMs do Instagram no estilo **ManyChat**: conecte uma conta
profissional do Instagram e dispare mensagens automáticas quando alguém
comentar em um post ou usar uma **palavra-chave**.

## Stack

| Camada     | Tecnologia                                      |
| ---------- | ----------------------------------------------- |
| Frontend   | Next.js 15 + React 19 + TypeScript + Tailwind   |
| Backend    | Python + FastAPI (async)                        |
| Banco      | Postgres (Supabase free tier)                   |
| ORM        | SQLAlchemy 2 async + psycopg3                    |
| Integração | Meta Graph API (Instagram)                      |
| Deploy     | Frontend → Vercel · Backend → Railway/Render    |

## Estrutura do backend (em camadas)

```
backend/
├── Dockerfile / Procfile / render.yaml   # deploy
├── requirements.txt
└── app/
    ├── main.py                 # entrypoint + lifespan (cria tabelas)
    ├── core/
    │   ├── config.py           # settings via .env (pydantic-settings)
    │   └── database.py         # engine async + Base + get_session
    ├── models/                 # ORM (SQLAlchemy)
    │   ├── account.py
    │   ├── automation.py
    │   └── message_log.py      # idempotência/auditoria
    ├── schemas/                # contratos da API (Pydantic)
    ├── crud/                   # acesso a dados isolado
    ├── services/
    │   ├── instagram_api.py    # cliente da Graph API
    │   └── automation_engine.py# regra: comentário → DM
    └── routers/
        ├── health.py
        ├── webhooks.py         # webhook da Meta (comentários)
        ├── instagram.py        # OAuth connect/callback
        └── automations.py      # CRUD de regras
```

**Fluxo principal:** webhook recebe comentário → `automation_engine.process_comment`
busca automações que casam (`crud.automation.find_matching`) → envia *private
reply* (vira DM) → registra em `message_logs` (evita responder 2x).

## Banco de dados — Supabase (free)

1. Crie um projeto em https://supabase.com (free tier).
2. Em **Project Settings → Database → Connection string**, copie a string de
   **Connection pooling (Transaction mode)**.
3. Troque o prefixo `postgresql://` por `postgresql+psycopg://` e use no
   `DATABASE_URL` do `.env`.

> O free tier pausa o projeto após ~1 semana de inatividade (reativa com 1 clique).

## Rodar local (após instalar Python e Node)

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # preencher DATABASE_URL e credenciais da Meta
uvicorn app.main:app --reload   # http://localhost:8000  (docs em /docs)
```

### Frontend

```powershell
cd frontend
npm install
copy .env.example .env.local
npm run dev                     # http://localhost:3000
```

## Deploy

- **Frontend → Vercel:** importe o repo, root `frontend/`, defina `BACKEND_URL`.
- **Backend → Railway ou Render:** usa o `Dockerfile`. No Render, o `render.yaml`
  já está pronto — preencha as env vars no painel. Configure `DATABASE_URL`,
  credenciais da Meta, `WEBHOOK_VERIFY_TOKEN` e `OAUTH_REDIRECT_URI`.

## Configuração da Meta

1. Crie um app em https://developers.facebook.com/apps e adicione **Instagram**.
2. Webhook → `https://SEU_BACKEND/webhooks/instagram` com o `WEBHOOK_VERIFY_TOKEN`.
3. Assine o campo **comments**.
4. Em dev, exponha o backend local com ngrok/cloudflared (a Meta exige HTTPS).
