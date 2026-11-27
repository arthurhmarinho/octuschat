"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { UserPlus } from "lucide-react";
import { Button, Card, Field, Input, Note, Spinner, StatusDot, useFeedback } from "@/components/ui";
import { formatDate, formatDateTime } from "@/lib/format";

type Status = "pending" | "awaiting_instagram" | "active" | "needs_reconnect";

type Person = {
  kind: "user" | "invite";
  status: Status;
  user_id: number | null;
  is_self: boolean;
  name: string | null;
  email: string | null;
  ig_username: string | null;
  accounts: { username: string | null; needs_reconnect: boolean }[];
  last_login_at: string | null;
  invite_id: number | null;
  meta_tester_added: boolean;
  expires_at: string | null;
};

type People = { people: Person[]; meta_app_id: string | null };

/** Um link recém-gerado, mostrado na linha de quem ele é. Some ao sair da tela. */
type Link = { row: string; url: string; note: string };

const STATUS: Record<Status, { label: string; tone: "positive" | "neutral" | "negative" }> = {
  pending: { label: "Convite pendente", tone: "neutral" },
  awaiting_instagram: { label: "Aguardando Instagram", tone: "neutral" },
  active: { label: "Ativa", tone: "positive" },
  needs_reconnect: { label: "Precisa reconectar", tone: "negative" },
};

const inviteRow = (id: number) => `invite:${id}`;
const rowKey = (p: Person) =>
  p.kind === "user" ? `user:${p.user_id}` : inviteRow(p.invite_id as number);

const signupUrl = (token: string) => `${window.location.origin}/cadastro?c=${token}`;
const resetUrl = (token: string) => `${window.location.origin}/redefinir-senha?c=${token}`;

const SIGNUP_NOTE = "Mande para a pessoa. Vale por 7 dias e serve uma vez";
const RESET_NOTE = "Mande para a pessoa. Vale por 24 horas e serve uma vez";

/** Chama o backend pelo proxy; erro vira exceção com a mensagem para a tela. */
async function call<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/backend${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new Error("Verifique a conexão e tente de novo");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(typeof data.detail === "string" ? data.detail : "Não foi possível concluir");
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

function LinkBox({ link }: { link: Link }) {
  const { toast } = useFeedback();

  async function copy() {
    try {
      await navigator.clipboard.writeText(link.url);
      toast("Link copiado");
    } catch {
      toast("Não foi possível copiar. Selecione o link e copie à mão", "error");
    }
  }

  return (
    <div className="mt-3 rounded-control border border-line-strong p-3">
      <p className="text-[13px] font-medium text-fg">Este link aparece só agora</p>
      <p className="mt-1 text-xs text-fg-3">{link.note}</p>
      <div className="mt-2 flex gap-2">
        <Input
          readOnly
          value={link.url}
          aria-label="Link gerado"
          onFocus={(e) => e.target.select()}
          className="min-w-0 flex-1 font-mono text-xs"
        />
        <Button variant="primary" onClick={copy}>
          Copiar
        </Button>
      </div>
    </div>
  );
}

function InviteForm({
  onCreated,
  onCancel,
}: {
  onCreated: (inviteId: number, token: string) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [ig, setIg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const handle = ig.trim().replace(/^@/, "").toLowerCase();
  const badHandle = handle.length > 0 && !/^[a-z0-9._]{1,30}$/.test(handle);
  const ready = !!name.trim() && handle.length > 0 && !badHandle;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!ready) return;
    setSaving(true);
    setError(null);
    try {
      const data = await call<{ invite: { id: number }; token: string }>("/admin/invites", "POST", {
        name,
        email: email.trim() || null,
        ig_username: handle,
      });
      onCreated(data.invite.id, data.token);
    } catch (err) {
      setError((err as Error).message);
      setSaving(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mt-4 space-y-4 border-t border-line pt-4">
      <div className="max-w-sm space-y-4">
        <Field label="Nome" htmlFor="invite-name">
          <Input
            id="invite-name"
            autoFocus
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        <Field label="E-mail (opcional)" htmlFor="invite-email">
          <Input
            id="invite-email"
            type="email"
            maxLength={255}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Field
          label="@ do Instagram"
          htmlFor="invite-ig"
          hint="A conta que a pessoa vai conectar"
          error={badHandle ? "Use letras, números, ponto e sublinhado (até 30)" : undefined}
        >
          <Input
            id="invite-ig"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            value={ig}
            onChange={(e) => setIg(e.target.value)}
          />
        </Field>
      </div>
      {error && (
        <p role="alert" className="text-[13px] text-negative">
          {error}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" variant="primary" size="sm" disabled={!ready || saving}>
          {saving ? "Criando" : "Criar convite"}
        </Button>
        <Button variant="ghost" size="sm" onClick={onCancel}>
          Fechar
        </Button>
      </div>
    </form>
  );
}

function details(p: Person): string {
  if (p.kind === "invite") {
    return `Convidado como @${p.ig_username}. O link vence em ${formatDate(p.expires_at)}`;
  }
  const accounts = p.accounts.map((a) => (a.username ? `@${a.username}` : "conta sem @")).join(", ");
  const parts = [
    accounts || (p.ig_username ? `Convidado como @${p.ig_username}` : "Sem conta conectada"),
    p.last_login_at ? `último acesso ${formatDateTime(p.last_login_at)}` : "nunca entrou",
  ];
  return parts.join(" · ");
}

/** Convites e pessoas com acesso ao painel. Só é montado para admin. */
export default function PeopleCard() {
  const { toast, confirm } = useFeedback();
  const [data, setData] = useState<People | null>(null);
  const [failed, setFailed] = useState(false);
  const [inviting, setInviting] = useState(false);
  const [link, setLink] = useState<Link | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await call<People>("/admin/people"));
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  /** Roda uma ação de linha: trava os botões, recarrega e mostra o erro num aviso. */
  async function run(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
    } catch (err) {
      toast((err as Error).message, "error");
    }
    await load();
    setBusy(false);
  }

  const markAdded = (p: Person) =>
    run(async () => {
      await call(`/admin/invites/${p.invite_id}/meta-added`, "POST");
    });

  const renew = (p: Person) =>
    run(async () => {
      const r = await call<{ invite: { id: number }; token: string }>(
        `/admin/invites/${p.invite_id}/renew`,
        "POST",
      );
      setLink({
        row: inviteRow(r.invite.id),
        url: signupUrl(r.token),
        note: `${SIGNUP_NOTE}. O link anterior deixou de valer`,
      });
    });

  async function cancel(p: Person) {
    const ok = await confirm({
      title: `Cancelar o convite de ${p.name ?? `@${p.ig_username}`}?`,
      description: "O link deixa de valer",
      confirmLabel: "Cancelar convite",
      cancelLabel: "Manter",
      tone: "danger",
    });
    if (!ok) return;
    await run(async () => {
      await call(`/admin/invites/${p.invite_id}`, "DELETE");
    });
  }

  const resetLink = (p: Person) =>
    run(async () => {
      const r = await call<{ token: string }>(`/admin/users/${p.user_id}/reset-link`, "POST");
      setLink({ row: rowKey(p), url: resetUrl(r.token), note: RESET_NOTE });
    });

  const rolesUrl = data?.meta_app_id
    ? `https://developers.facebook.com/apps/${data.meta_app_id}/roles/roles/`
    : "https://developers.facebook.com/apps/";

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-[15px] font-medium text-fg">Pessoas</h2>
          <p className="mt-1 text-sm text-fg-2">Quem tem acesso ao painel</p>
        </div>
        {!inviting && (
          <Button variant="secondary" size="sm" icon={UserPlus} onClick={() => setInviting(true)}>
            Convidar pessoa
          </Button>
        )}
      </div>

      {inviting && (
        <InviteForm
          onCancel={() => setInviting(false)}
          onCreated={(id, token) => {
            setInviting(false);
            setLink({ row: inviteRow(id), url: signupUrl(token), note: SIGNUP_NOTE });
            load();
          }}
        />
      )}

      {!data ? (
        failed ? (
          <Note variant="warning" className="mt-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span>Não foi possível carregar a lista</span>
              <Button variant="secondary" size="sm" onClick={load}>
                Tentar de novo
              </Button>
            </div>
          </Note>
        ) : (
          <div className="py-6">
            <Spinner />
          </div>
        )
      ) : (
        <ul className="mt-4 divide-y divide-line border-t border-line">
          {data.people.map((p) => {
            const key = rowKey(p);
            const metaTask =
              !!p.invite_id &&
              !p.meta_tester_added &&
              (p.status === "pending" || p.status === "awaiting_instagram");
            return (
              <li key={key} className="py-4 last:pb-0">
                <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-fg">
                      {p.name}
                      {p.is_self && <span className="font-normal text-fg-3"> (você)</span>}
                    </p>
                    {p.email && <p className="truncate text-[13px] text-fg-2">{p.email}</p>}
                  </div>
                  <span className="flex items-center gap-2 text-xs text-fg-2">
                    <StatusDot tone={STATUS[p.status].tone} />
                    {STATUS[p.status].label}
                  </span>
                </div>
                <p className="mt-1 break-words text-[13px] text-fg-3">{details(p)}</p>

                {metaTask && (
                  <Note className="mt-3">
                    <p>
                      Adicione <span className="font-medium text-fg">@{p.ig_username}</span> como
                      Testador do Instagram em{" "}
                      <a href={rolesUrl} target="_blank" rel="noreferrer" className="text-fg underline">
                        Funções do app na Meta
                      </a>
                    </p>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={busy}
                      onClick={() => markAdded(p)}
                      className="mt-2"
                    >
                      Já adicionei
                    </Button>
                  </Note>
                )}

                {link?.row === key && <LinkBox link={link} />}

                {p.kind === "invite" ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button variant="secondary" size="sm" disabled={busy} onClick={() => renew(p)}>
                      Copiar novo link
                    </Button>
                    <Button variant="danger" size="sm" disabled={busy} onClick={() => cancel(p)}>
                      Cancelar
                    </Button>
                  </div>
                ) : (
                  !p.is_self && (
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={busy}
                      onClick={() => resetLink(p)}
                      className="-ml-3 mt-2"
                    >
                      Gerar link de redefinição de senha
                    </Button>
                  )
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
