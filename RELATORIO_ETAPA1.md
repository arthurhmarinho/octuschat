# Relatório da Etapa 1 — Multiusuário (branch `feat/multiusuario`)

Base: `main` (7df188c). Sem merge nem push na `main`. Sem trailer Co-Authored-By.

## O que foi feito, por parte

| Parte | Commit | Resumo |
|---|---|---|
| M.0 | `69a83b1` | Tabela `users` (scrypt), `instagram_accounts.owner_user_id` e `token_invalid_at`, migração **0005** (sobe, desce e sobe de novo sem divergência de schema), `crud.user`, `crud.account` com `list_by_owner`, `get_owned` e `upsert` com `AccountOwnedByOther`. |
| M.1 | `0560251` | `python -m scripts.create_user` (`--admin`, `--claim-orphans`, `--reset-password`). Senha temporária impressa uma vez, `must_change_password=true`. |
| M.2 | `a09522b` | `POST /auth/login` (401 genérico, igual para e-mail inexistente e senha errada, com custo de scrypt equalizado), `GET /auth/me`, `POST /auth/password`. `current_user` (segredo + `X-Octus-User`). `state` do OAuth com uid assinado (`<ts>.<nonce>.<uid>.<hmac>`); o formato antigo é recusado. |
| M.3 | `c552194` | Todas as rotas protegidas passam por `current_user` e `owned_account` (404 para conta alheia, igual ao de conta inexistente). Callback grava o dono; `?connected=error&reason=owned` quando a conta é de outro. Zera `token_invalid_at` ao conectar. |
| M.4 | `ef379a6` | `InstagramAPIError.code`; código 190 marca `token_invalid_at` (envio, resposta pública, mídia e renovação); renovação bem-sucedida limpa; renovação proativa no worker (1ª passagem ao subir e depois a cada 12 h, janela de 15 dias, ignora contas já recusadas); `AccountRead` com `token_expires_at` e `needs_reconnect`. |
| M.5 | `24fdbee` | Sessão `<uid>.<exp>.<hmac>` (formato antigo recusado), login por e-mail via backend, proxy injeta `X-Octus-User` da sessão e nunca repassa o do browser, `/api/auth/me`, tela de login nova, `/primeiro-acesso`, `useAccount` com seletor e `localStorage` (`octus.account`), rodapé da sidebar com usuário, seletor e ponto de status, Configurações (Sua conta, Instagram, aviso `owned`), banner de reconexão e 3 passos no Início. |
| M.6 | `c55e482` | Verificação ponta a ponta, correção de uma corrida no primeiro acesso e README (usuários, convite, "Como adicionar um testador", deploy). |

## Testes

- **pytest completo com Postgres descartável (podman, porta 55432): 255 passed.** Antes da etapa eram 175 (149 sem banco + 26 de banco). Novos: `test_passwords`, `test_users_crud`, `test_create_user_script`, `test_routes_ownership` (27 casos de rota com dois usuários), `test_token_health`, mais casos em `test_auth` e `test_engine_graph`.
- **`npx tsc --noEmit`:** sem erros. **`npm run build`** (com o dev parado): passa.
- **Ponta a ponta com Playwright** (backend na 8001 → Postgres descartável; frontend na 3100 com `BACKEND_URL=http://localhost:8001` por variável de ambiente): **25 verificações ok, 0 falhas, sem erro de página.** Cobre:
  - senha errada e e-mail inexistente com a mesma mensagem;
  - senha temporária leva a `/primeiro-acesso`, e as outras páginas redirecionam para lá;
  - botão bloqueado com senha curta;
  - depois da troca vai para `/configuracoes`;
  - A vê só os dados de A, e B só os de B;
  - o seletor de conta recarrega os dados e persiste após recarregar;
  - `X-Octus-User` forjado é ignorado, e o proxy usa o usuário da sessão;
  - cookie de 2 partes (formato antigo) leva ao login e dá 401 no proxy;
  - a senha temporária deixa de valer depois da troca, e a nova entra direto;
  - B recebe 404 na conta de A, e B (1 conta) não tem menu de seletor;
  - banner "Reconectar Instagram" e ponto vermelho com `token_invalid_at` marcado.
- Screenshots (no scratchpad da sessão): `m6-login-erro`, `m6-primeiro-acesso`, `m6-config-a`, `m6-seletor`, `m6-inicio-a`, `m6-inicio-b`, `m6-reconnect`.

## Diferenças em relação ao plano

- **Bug achado e corrigido na M.6:** logo depois de trocar a senha no primeiro acesso, um efeito de "já trocou, vá para `/`" corria contra o redirecionamento para `/configuracoes`. Agora o destino correto vence.
- **Sem backend enforcement de `must_change_password`:** como no plano, o redirecionamento é só do frontend (AppShell). Quem chamar a API diretamente com sessão válida consegue operar com a senha temporária.
- **`/api/auth/me` é redundante** com `/api/backend/auth/me` (o proxy genérico também serve), mas foi criado como o plano pede.
- **Regra "não-demo" removida** do `account.ts`, do Início e das Configurações: a conta `demo` agora é uma conta como as outras, e o seletor deixa escolher. Depois de `--claim-orphans`, `demo` vai para o dono.
- O primeiro `Skeleton`/`Feedback` da branch `ui/melhorias-ux` **não existe** nesta branch (ela sai da `main`); as telas novas usam `Spinner`.
- A migração roda em Supabase com `alembic upgrade head`; **não foi aplicada em produção** (só no Postgres descartável).

## Precisa de teste ao vivo

- Fluxo OAuth real (conectar uma conta, `reason=owned` com duas contas reais).
- Resposta real da Meta com código 190 (hoje coberta com mock).
- Renovação proativa contra a Meta (mock).

## Comandos de deploy (seção 6 do plano)

1. Revisar `feat/multiusuario` e confirmar os testes.
2. Merge na `main` e push. Render e Vercel sobem juntos; o Render roda `alembic upgrade head` (0005).
3. Assim que o Render terminar, contra o banco de produção:
   `cd backend && .venv/bin/python -m scripts.create_user --email <dono> --name "Arthur" --admin --claim-orphans`
4. Vercel: remover `ADMIN_PASSWORD`. Manter `SESSION_SECRET`, `BACKEND_URL` e `BACKEND_API_SECRET`.
5. Entrar com e-mail e a senha temporária, trocar a senha e reconectar o Instagram (o token atual foi invalidado, código 190).
6. Seguir "Como adicionar um testador" no README.

Entre o deploy e o passo 3 ninguém consegue entrar.
