"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { Check } from "lucide-react";
import AppShell from "@/components/AppShell";
import ConnectNotice from "@/components/ConnectNotice";
import { Button, Card, Note, Skeleton, StatusDot, cx } from "@/components/ui";
import { useAccount } from "@/lib/account";
import { useChecks, useOnboarding } from "@/lib/onboarding";
import { useUser } from "@/lib/user";

const CONNECT = "/api/backend/instagram/connect";
const TESTER_INVITES = "https://www.instagram.com/accounts/manage_access/";

type StepState = "done" | "current" | "pending";

const STATE_LABEL: Record<StepState, string> = {
  done: "feito",
  current: "passo atual",
  pending: "pendente",
};

function Step({
  number,
  title,
  state,
  children,
}: {
  number: number;
  title: string;
  state: StepState;
  children: ReactNode;
}) {
  return (
    <li
      className="flex gap-3 border-b border-line p-5 last:border-b-0"
      aria-current={state === "current" ? "step" : undefined}
    >
      <span
        aria-hidden
        className={cx(
          "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border font-mono text-xs",
          state === "done" && "border-line-strong text-positive",
          state === "current" && "border-fg bg-fg text-on-fg",
          state === "pending" && "border-line-strong text-fg-3",
        )}
      >
        {state === "done" ? <Check size={12} strokeWidth={2} /> : number}
      </span>
      <div className="min-w-0 flex-1 space-y-3">
        <h2 className={cx("text-[15px] font-medium", state === "pending" ? "text-fg-2" : "text-fg")}>
          {title}
          <span className="sr-only"> ({STATE_LABEL[state]})</span>
        </h2>
        {children}
      </div>
    </li>
  );
}

const Text = ({ children }: { children: ReactNode }) => (
  <p className="text-sm leading-6 text-fg-2">{children}</p>
);

function Checkbox({
  checked,
  onChange,
  children,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  children: ReactNode;
}) {
  return (
    <label className="flex w-fit cursor-pointer items-center gap-2 text-sm text-fg">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 accent-fg"
      />
      {children}
    </label>
  );
}

export default function ConectarPage() {
  const { user } = useUser();
  const { data, failed, reload } = useOnboarding();
  const { checks, toggle } = useChecks(user?.id);
  const { refreshAccounts, setAccountId } = useAccount();
  const selected = useRef(false);

  // Voltando de uma conexão que deu certo: recarrega o seletor de conta e
  // deixa selecionada a conta conectada por último.
  useEffect(() => {
    if (!data || selected.current) return;
    selected.current = true;
    if (new URLSearchParams(window.location.search).get("connected") !== "ok") return;
    const newest = [...data.accounts].sort(
      (a, b) => Date.parse(b.connected_at) - Date.parse(a.connected_at),
    )[0];
    refreshAccounts().then(() => newest && setAccountId(newest.ig_user_id));
  }, [data, refreshAccounts, setAccountId]);

  if (!data) {
    return (
      <AppShell title="Conectar Instagram">
        <div className="max-w-2xl">
          <ConnectNotice />
          {failed ? (
            <Note variant="warning">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span>Não foi possível falar com o servidor</span>
                <Button variant="secondary" size="sm" onClick={reload}>
                  Tentar de novo
                </Button>
              </div>
            </Note>
          ) : (
            <Skeleton className="h-[420px] rounded-card" />
          )}
        </div>
      </AppShell>
    );
  }

  const { accounts, meta_tester_added: testerAdded } = data;
  const invited = data.invited_ig_username;
  const working = accounts.filter((a) => !a.needs_reconnect);
  const broken = accounts.filter((a) => a.needs_reconnect);
  const connected = working.length > 0;
  const waitingOwner = !connected && !!invited && !testerAdded;
  const handle = (username: string | null) => (username ? `@${username}` : "sua conta");
  const names = working.map((a) => handle(a.username)).join(", ");
  // Conectou, mas nenhuma das contas é a do convite: só avisa.
  const mismatch =
    !!invited && connected && !accounts.some((a) => a.username?.toLowerCase() === invited);

  // 1 e 4 são marcados pela pessoa; 2, 3 e 5 vêm da API. A Meta só conecta
  // conta profissional, então conectar também conclui o 1.
  const done = [connected || checks.professional, connected, connected, checks.messages, connected];
  const current = done.indexOf(false);
  const stateOf = (i: number): StepState => (done[i] ? "done" : i === current ? "current" : "pending");

  return (
    <AppShell title="Conectar Instagram">
      <div className="max-w-2xl">
        <ConnectNotice />
        {mismatch && (
          <Note className="mb-4">
            Você conectou {handle(working[0].username)}, e o convite era para @{invited}
          </Note>
        )}
        <Card padding="none">
          <ol>
            <Step number={1} title="Conta profissional" state={stateOf(0)}>
              <Text>
                {invited ? `Sua conta @${invited}` : "Sua conta"} precisa ser Profissional (Criador
                ou Empresa)
              </Text>
              {!connected && (
                <>
                  <Text>
                    Para mudar, no Instagram: Configurações → Tipo de conta e ferramentas → Mudar
                    para conta profissional
                  </Text>
                  <Checkbox
                    checked={checks.professional}
                    onChange={(v) => toggle("professional", v)}
                  >
                    Minha conta já é profissional
                  </Checkbox>
                </>
              )}
            </Step>

            <Step number={2} title="Aceite o convite de testador" state={stateOf(1)}>
              {connected ? (
                <Text>Convite aceito</Text>
              ) : waitingOwner ? (
                <>
                  <Text>
                    Aguardando quem te convidou liberar seu @ na Meta. Avise essa pessoa e volte
                    aqui depois
                  </Text>
                  <Button variant="secondary" size="sm" onClick={reload}>
                    Verificar de novo
                  </Button>
                </>
              ) : (
                <>
                  <Text>
                    Abra a página abaixo, entre na aba <span className="text-fg">Convites de testador</span>{" "}
                    e toque em Aceitar.{" "}
                    {invited ? `Confira se você está logado em @${invited}` : "Confira se você está logado na conta certa"}
                  </Text>
                  {!invited && (
                    <Text>
                      Se não houver convite, quem administra o painel ainda precisa adicionar seu @
                      como Testador do Instagram na Meta
                    </Text>
                  )}
                  <a
                    href={TESTER_INVITES}
                    target="_blank"
                    rel="noreferrer"
                    className="block break-all text-sm text-fg underline"
                  >
                    {TESTER_INVITES}
                  </a>
                </>
              )}
            </Step>

            <Step number={3} title="Conectar Instagram" state={stateOf(2)}>
              {connected ? (
                <Button variant="ghost" size="sm" href={CONNECT} className="-ml-3">
                  Conectar outra conta
                </Button>
              ) : (
                <>
                  {broken.length > 0 && (
                    <Note variant="warning">
                      A Meta recusou o acesso de {broken.map((a) => handle(a.username)).join(", ")}.
                      Conecte de novo
                    </Note>
                  )}
                  {waitingOwner && (
                    <Note variant="warning">
                      Seu @ ainda não foi marcado como liberado. Se tentar agora, a Meta pode
                      mostrar um erro
                    </Note>
                  )}
                  <Button variant={waitingOwner ? "secondary" : "primary"} href={CONNECT}>
                    Conectar Instagram
                  </Button>
                  <Text>
                    Se a Meta mostrar um erro de permissão ou “Insufficient developer role”, o
                    convite de testador ainda não foi aceito (passo 2)
                  </Text>
                </>
              )}
            </Step>

            <Step number={4} title="Permita o acesso às mensagens" state={stateOf(3)}>
              <Text>
                No Instagram: Configurações → Mensagens e respostas aos stories → Ferramentas
                conectadas → <span className="text-fg">Permitir acesso às mensagens</span>. Sem
                isso, as DMs não chegam
              </Text>
              <Checkbox checked={checks.messages} onChange={(v) => toggle("messages", v)}>
                Já permiti o acesso às mensagens
              </Checkbox>
            </Step>

            <Step number={5} title="Pronto" state={stateOf(4)}>
              {connected ? (
                <>
                  <p className="flex items-center gap-2 text-sm text-fg">
                    <StatusDot tone="positive" />
                    <span>
                      {names} {working.length > 1 ? "conectadas" : "conectada"}
                    </span>
                  </p>
                  {!checks.messages && <Text>Não esqueça do passo 4 para receber as DMs</Text>}
                  <Button variant="primary" href="/automations/new">
                    Criar minha primeira automação
                  </Button>
                </>
              ) : (
                <Text>Aparece quando a conta estiver conectada</Text>
              )}
            </Step>
          </ol>
        </Card>
      </div>
    </AppShell>
  );
}
