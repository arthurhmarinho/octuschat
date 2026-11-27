"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MessagesSquare, Workflow } from "lucide-react";
import AppShell from "@/components/AppShell";
import Avatar from "@/components/Avatar";
import ConnectNotice from "@/components/ConnectNotice";
import {
  Button,
  Card,
  EmptyState,
  KeywordTokens,
  Note,
  Skeleton,
  StatusDot,
  cx,
} from "@/components/ui";
import { useAccount } from "@/lib/account";
import { TRIGGER_TEXT, sourceLabel, type Trigger } from "@/lib/automation";
import { dayKey, formatDate, formatRelative } from "@/lib/format";

type Automation = {
  id: number;
  name: string;
  trigger: Trigger;
  keyword: string | null;
  enabled: boolean;
};
type Contact = {
  id: number;
  ig_user_id: string;
  username: string | null;
  profile_pic: string | null;
  last_message_at: string | null;
};
type ContactRow = { first_seen: string };
type Message = { id: number; direction: "in" | "out"; text: string; source: string; created_at: string };
type Conversation = { contact: Contact; messages: Message[] };

type Data = {
  automations: Automation[];
  contacts: ContactRow[];
  conversations: Conversation[];
};

const DAY = 86400000;
const WINDOW_DAYS = 7;

/** Quantos itens caem em [now-7d, now) e em [now-14d, now-7d). */
function countWindows(dates: string[], now: number): { current: number; previous: number } {
  let current = 0;
  let previous = 0;
  for (const d of dates) {
    const age = now - new Date(d).getTime();
    if (age < 0) continue;
    if (age < WINDOW_DAYS * DAY) current++;
    else if (age < 2 * WINDOW_DAYS * DAY) previous++;
  }
  return { current, previous };
}

/** "+3 vs 7 dias anteriores", "2 a menos vs 7 dias anteriores" ou "igual aos 7 dias anteriores". */
function deltaText(current: number, previous: number): string {
  const diff = current - previous;
  if (diff === 0) return "igual aos 7 dias anteriores";
  return diff > 0 ? `+${diff} vs 7 dias anteriores` : `${-diff} a menos vs 7 dias anteriores`;
}

const nameOf = (c: Contact) => (c.username ? `@${c.username}` : `usuário ${c.ig_user_id}`);

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

function Stat({
  label,
  value,
  meta,
  note,
}: {
  label: string;
  value: number;
  meta?: string;
  note?: string;
}) {
  return (
    <Card className="flex flex-col gap-3">
      <p className="text-[13px] text-fg-2">{label}</p>
      <p className="flex items-baseline gap-2">
        <span className="text-[28px] font-medium leading-none tabular-nums text-fg">{value}</span>
        {meta && <span className="text-[13px] text-fg-3">{meta}</span>}
      </p>
      {note && <p className="text-xs text-fg-3">{note}</p>}
    </Card>
  );
}

type Day = { key: string; date: Date; sent: number; received: number };

/** Mensagens por dia nos últimos 14 dias, do mais antigo ao mais recente. */
function lastDays(conversations: Conversation[], n = 14, now = new Date()): Day[] {
  const days: Day[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i);
    days.push({ key: dayKey(date), date, sent: 0, received: 0 });
  }
  const byKey = new Map(days.map((d) => [d.key, d]));
  for (const c of conversations) {
    for (const m of c.messages) {
      const day = byKey.get(dayKey(m.created_at));
      if (!day) continue;
      if (m.direction === "out") day.sent++;
      else day.received++;
    }
  }
  return days;
}

const WEEKDAY = new Intl.DateTimeFormat("pt-BR", { weekday: "short" });

/** Gráfico principal: barras empilhadas, enviadas em destaque e recebidas em cinza. */
function Activity({ days }: { days: Day[] }) {
  const max = Math.max(1, ...days.map((d) => d.sent + d.received));
  const total = days.reduce((n, d) => n + d.sent + d.received, 0);
  const H = 120;

  return (
    <Card padding="none">
      <div className="flex h-12 items-center justify-between border-b border-line px-5">
        <h2 className="text-[15px] font-medium text-fg">Atividade</h2>
        <div className="flex items-center gap-4 text-xs text-fg-3">
          <span className="flex items-center gap-1.5">
            <span aria-hidden className="h-2 w-2 rounded-[2px] bg-fg" />
            Enviadas
          </span>
          <span className="flex items-center gap-1.5">
            <span aria-hidden className="h-2 w-2 rounded-[2px] bg-fg-3/60" />
            Recebidas
          </span>
        </div>
      </div>

      {total === 0 ? (
        <p className="px-5 py-10 text-center text-sm text-fg-3">
          Nenhuma mensagem nos últimos 14 dias
        </p>
      ) : (
        <div className="px-5 pb-4 pt-5">
          <ul className="flex items-end gap-1.5 sm:gap-2" style={{ height: H }}>
            {days.map((d, i) => {
              const sentH = Math.round((d.sent / max) * H);
              const recvH = Math.round((d.received / max) * H);
              const today = i === days.length - 1;
              return (
                <li
                  key={d.key}
                  className="group relative flex h-full min-w-0 flex-1 flex-col justify-end"
                  title={`${formatDate(d.date)}: ${d.sent} enviadas, ${d.received} recebidas`}
                  aria-label={`${formatDate(d.date)}: ${d.sent} enviadas, ${d.received} recebidas`}
                >
                  {/* mínimo de 2px quando há valor, para não sumir */}
                  {d.received > 0 && (
                    <div
                      className="w-full rounded-t-[3px] bg-fg-3/60 transition-colors duration-150 group-hover:bg-fg-3"
                      style={{ height: Math.max(2, recvH) }}
                    />
                  )}
                  {d.sent > 0 && (
                    <div
                      className={cx(
                        "w-full bg-fg transition-opacity duration-150 group-hover:opacity-80",
                        d.received === 0 ? "rounded-t-[3px]" : "mt-px"
                      )}
                      style={{ height: Math.max(2, sentH) }}
                    />
                  )}
                  {d.sent + d.received === 0 && <div className="h-px w-full bg-line-strong" />}
                </li>
              );
            })}
          </ul>
          <ul aria-hidden className="mt-2 flex gap-1.5 sm:gap-2">
            {days.map((d, i) => {
              const fromEnd = days.length - 1 - i;
              // Larga: um rótulo a cada 2 dias. Estreita: a cada 4, para não cortar.
              const cls =
                fromEnd % 4 === 0 ? "" : fromEnd % 2 === 0 ? "invisible sm:visible" : "invisible";
              return (
                <li
                  key={d.key}
                  className={cx(
                    "flex min-w-0 flex-1 justify-center font-mono text-[11px]",
                    fromEnd === 0 ? "text-fg-2" : "text-fg-3",
                    cls
                  )}
                >
                  <span className="whitespace-nowrap">{WEEKDAY.format(d.date).replace(".", "")}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </Card>
  );
}

function SectionHead({ title, href, linkLabel = "Ver todas" }: { title: string; href: string; linkLabel?: string }) {
  return (
    <div className="flex h-12 items-center justify-between border-b border-line px-5">
      <h2 className="text-[15px] font-medium text-fg">{title}</h2>
      <Link href={href} className="text-[13px] text-fg-2 transition-colors duration-150 hover:text-fg">
        {linkLabel}
      </Link>
    </div>
  );
}

export default function Home() {
  const { account, resolved } = useAccount();
  const [data, setData] = useState<Data | null>(null);
  const [serverDown, setServerDown] = useState(false);

  const accountId = account?.ig_user_id ?? null;

  // Servidor fora: sem conta resolvida não dá para distinguir "sem conta" de
  // "sem resposta", então testamos o health quando não há conta.
  useEffect(() => {
    if (!resolved || accountId) return;
    fetch("/api/backend/health")
      .then((r) => setServerDown(!r.ok))
      .catch(() => setServerDown(true));
  }, [resolved, accountId]);

  useEffect(() => {
    if (!accountId) return;
    setData(null); // trocou de conta: não mostra os dados da anterior
    const q = `account_id=${accountId}`;
    Promise.all([
      getJson<Automation[]>(`/api/backend/automations?${q}`),
      getJson<ContactRow[]>(`/api/backend/contacts?${q}`),
      getJson<Conversation[]>(`/api/backend/conversations?${q}`),
    ])
      .then(([automations, contacts, conversations]) =>
        setData({ automations, contacts, conversations })
      )
      .catch(() => setServerDown(true));
  }, [accountId]);

  if (!resolved || (accountId && !data && !serverDown)) {
    return (
      <AppShell title="Início">
        <div aria-busy="true" aria-label="Carregando">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-[116px] rounded-card" />
            ))}
          </div>
          <Skeleton className="mt-4 h-[236px] rounded-card" />
        </div>
      </AppShell>
    );
  }

  if (serverDown) {
    return (
      <AppShell title="Início">
        <Note variant="warning">
          Não foi possível falar com o servidor. Tente de novo em alguns segundos
        </Note>
      </AppShell>
    );
  }

  if (!accountId || !data) {
    return (
      <AppShell title="Início">
        <ConnectNotice />
        <Card className="max-w-xl">
          <h2 className="text-[15px] font-medium text-fg">Conecte sua conta do Instagram</h2>
          <p className="mb-4 mt-1 text-sm text-fg-2">
            Depois de conectar, suas automações, contatos e conversas aparecem aqui
          </p>
          <Button variant="primary" href="/conectar">
            Continuar configuração
          </Button>
        </Card>
      </AppShell>
    );
  }

  const { automations, conversations } = data;
  const active = automations.filter((a) => a.enabled).length;
  const now = Date.now();
  const allMessages = conversations.flatMap((c) => c.messages);
  const sent = countWindows(
    allMessages.filter((m) => m.direction === "out").map((m) => m.created_at),
    now
  );
  const received = countWindows(
    allMessages.filter((m) => m.direction === "in").map((m) => m.created_at),
    now
  );
  const newContacts = countWindows(data.contacts.map((c) => c.first_seen), now);
  const days = lastDays(conversations);
  const recent = conversations.filter((c) => c.messages.length).slice(0, 6);
  const topAutomations = automations.slice(0, 6);

  return (
    <AppShell title="Início">
      <ConnectNotice />
      {account?.needs_reconnect && (
        <Note variant="warning" className="mb-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>
              O Instagram recusou o acesso de @{account.username ?? account.ig_user_id}. As
              automações não respondem até você reconectar
            </span>
            <Button variant="secondary" size="sm" href="/api/backend/instagram/connect">
              Reconectar Instagram
            </Button>
          </div>
        </Note>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Automações ativas" value={active} meta={`de ${automations.length}`} />
        <Stat
          label="Respostas enviadas"
          value={sent.current}
          meta="7 dias"
          note={deltaText(sent.current, sent.previous)}
        />
        <Stat
          label="Mensagens recebidas"
          value={received.current}
          meta="7 dias"
          note={deltaText(received.current, received.previous)}
        />
        <Stat
          label="Contatos novos"
          value={newContacts.current}
          meta="7 dias"
          note={deltaText(newContacts.current, newContacts.previous)}
        />
      </div>

      <div className="mt-4">
        <Activity days={days} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[2fr_1fr]">
        {/* Últimas conversas */}
        <Card padding="none" className="min-w-0">
          <SectionHead title="Últimas conversas" href="/conversas" />
          {recent.length === 0 ? (
            <EmptyState
              icon={MessagesSquare}
              title="Nenhuma conversa ainda"
              description="As mensagens trocadas com seus contatos aparecem aqui"
            />
          ) : (
            <ul>
              {recent.map((c) => {
                const last = c.messages[c.messages.length - 1];
                return (
                  <li key={c.contact.id} className="border-b border-line last:border-b-0">
                    <Link
                      href={`/conversas?c=${c.contact.id}`}
                      className="flex h-14 items-center gap-3 px-5 transition-colors duration-150 hover:bg-raised/50"
                    >
                      <Avatar src={c.contact.profile_pic} name={nameOf(c.contact)} size={32} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-fg">{nameOf(c.contact)}</p>
                        <p className="truncate text-[13px] text-fg-2">
                          {last.direction === "out" ? "Você: " : ""}
                          {last.text}
                        </p>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className="font-mono text-xs text-fg-3">{formatRelative(last.created_at)}</p>
                        <p className="text-xs text-fg-3">{sourceLabel(last.source)}</p>
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        {/* Automações */}
        <Card padding="none" className="min-w-0 self-start">
          <SectionHead title="Automações" href="/automations" />
          {topAutomations.length === 0 ? (
            <EmptyState
              icon={Workflow}
              title="Nenhuma automação"
              description="Responda comentários e DMs automaticamente"
              action={
                <Button variant="secondary" size="sm" href="/automations/new">
                  Nova automação
                </Button>
              }
            />
          ) : (
            <ul>
              {topAutomations.map((a) => {
                const showKeyword =
                  a.keyword && (a.trigger === "comment_keyword" || a.trigger === "dm_keyword" || a.trigger === "story_reply");
                return (
                  <li key={a.id} className="border-b border-line last:border-b-0">
                    <Link
                      href={`/automations/${a.id}/edit`}
                      className="flex items-start gap-3 px-5 py-3 transition-colors duration-150 hover:bg-raised/50"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm text-fg">{a.name || "Sem nome"}</p>
                        <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-2">
                          {TRIGGER_TEXT[a.trigger]}
                          {showKeyword && <KeywordTokens value={a.keyword} />}
                        </p>
                      </div>
                      <span className="mt-1.5 flex items-center gap-2 text-xs text-fg-3">
                        <StatusDot tone={a.enabled ? "positive" : "neutral"} />
                        {a.enabled ? "Ativa" : "Pausada"}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
