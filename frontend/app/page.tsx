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
  Spinner,
  StatusDot,
} from "@/components/ui";
import { useAccount } from "@/lib/account";
import { TRIGGER_TEXT, sourceLabel, type Trigger } from "@/lib/automation";
import { formatRelative } from "@/lib/format";

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
type Message = { id: number; direction: "in" | "out"; text: string; source: string; created_at: string };
type Conversation = { contact: Contact; messages: Message[] };

type Data = {
  automations: Automation[];
  contacts: number;
  conversations: Conversation[];
};

const nameOf = (c: Contact) => (c.username ? `@${c.username}` : `usuário ${c.ig_user_id}`);

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

function Stat({ label, value, meta }: { label: string; value: number; meta?: string }) {
  return (
    <Card className="flex flex-col gap-3">
      <p className="text-[13px] text-fg-2">{label}</p>
      <p className="flex items-baseline gap-2">
        <span className="text-[28px] font-medium leading-none tabular-nums text-fg">{value}</span>
        {meta && <span className="text-[13px] text-fg-3">{meta}</span>}
      </p>
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

  const accountId = account && account.ig_user_id !== "demo" ? account.ig_user_id : null;

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
    const q = `account_id=${accountId}`;
    Promise.all([
      getJson<Automation[]>(`/api/backend/automations?${q}`),
      getJson<unknown[]>(`/api/backend/contacts?${q}`),
      getJson<Conversation[]>(`/api/backend/conversations?${q}`),
    ])
      .then(([automations, contacts, conversations]) =>
        setData({ automations, contacts: contacts.length, conversations })
      )
      .catch(() => setServerDown(true));
  }, [accountId]);

  if (!resolved || (accountId && !data && !serverDown)) {
    return (
      <AppShell title="Início">
        <div className="flex justify-center py-24">
          <Spinner />
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
            Depois de conectar, suas automações, contatos e conversas aparecem aqui.
          </p>
          <Button variant="primary" href="/api/backend/instagram/connect">
            Conectar Instagram
          </Button>
        </Card>
      </AppShell>
    );
  }

  const { automations, conversations } = data;
  const active = automations.filter((a) => a.enabled).length;
  const recent = conversations.filter((c) => c.messages.length).slice(0, 6);
  const topAutomations = automations.slice(0, 6);

  return (
    <AppShell title="Início">
      <ConnectNotice />
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Automações ativas" value={active} meta={`de ${automations.length}`} />
        <Stat label="Contatos" value={data.contacts} />
        <Stat label="Conversas" value={conversations.length} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[2fr_1fr]">
        {/* Últimas conversas */}
        <Card padding="none">
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
        <Card padding="none" className="self-start">
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
