"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { MessagesSquare } from "lucide-react";
import AppShell from "@/components/AppShell";
import Avatar from "@/components/Avatar";
import { Card, EmptyState, Note, Spinner, cx } from "@/components/ui";
import { useAccount } from "@/lib/account";
import { sourceLabel } from "@/lib/automation";
import { formatRelative, formatTime } from "@/lib/format";

type Message = {
  id: number;
  direction: "in" | "out";
  text: string;
  source: string;
  created_at: string;
};
type Contact = {
  id: number;
  ig_user_id: string;
  username: string | null;
  profile_pic: string | null;
  last_message_at: string | null;
};
type Conversation = {
  contact: Contact;
  messages: Message[];
};

const nameOf = (c: Contact) => (c.username ? `@${c.username}` : `usuário ${c.ig_user_id}`);

function Conversas() {
  const { accountId, resolved } = useAccount();
  const params = useSearchParams();
  const wanted = Number(params.get("c")) || null;
  const [convos, setConvos] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!resolved) return;
    if (!accountId) {
      setLoading(false);
      return;
    }
    fetch(`/api/backend/conversations?account_id=${accountId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: Conversation[]) => {
        setConvos(data);
        const target = data.find((c) => c.contact.id === wanted) ?? data[0];
        if (target) setSelected(target.contact.id);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
    // `wanted` só vale na abertura da página.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId, resolved]);

  const current = convos.find((c) => c.contact.id === selected);

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Spinner />
      </div>
    );
  }
  if (error) {
    return (
      <Note variant="warning">
        Não foi possível carregar as conversas. Verifique a conexão e tente de novo
      </Note>
    );
  }
  if (convos.length === 0) {
    return (
      <Card padding="none">
        <EmptyState
          icon={MessagesSquare}
          title="Nenhuma conversa ainda"
          description="As mensagens trocadas com seus contatos aparecem aqui"
        />
      </Card>
    );
  }

  return (
    <Card padding="none" className="flex min-h-0 flex-1 overflow-hidden">
      {/* Lista */}
      <div className="w-[300px] shrink-0 overflow-y-auto border-r border-line">
        {convos.map((c) => {
          const last = c.messages[c.messages.length - 1];
          const active = c.contact.id === selected;
          return (
            <button
              key={c.contact.id}
              type="button"
              onClick={() => setSelected(c.contact.id)}
              aria-current={active ? "true" : undefined}
              className={cx(
                "flex h-14 w-full items-center gap-3 border-b border-line px-4 text-left",
                "transition-colors duration-150 ease-out",
                active ? "bg-raised" : "hover:bg-raised/50"
              )}
            >
              <Avatar src={c.contact.profile_pic} name={nameOf(c.contact)} size={32} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-fg">{nameOf(c.contact)}</p>
                <p className="truncate text-[13px] text-fg-2">
                  {last ? (last.direction === "out" ? "Você: " : "") + last.text : ""}
                </p>
              </div>
              {last && (
                <span className="shrink-0 font-mono text-xs text-fg-3">
                  {formatRelative(last.created_at)}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Thread */}
      <div className="flex min-w-0 flex-1 flex-col">
        {current ? (
          <>
            <div className="flex h-14 shrink-0 items-center gap-3 border-b border-line px-5">
              <Avatar src={current.contact.profile_pic} name={nameOf(current.contact)} size={32} />
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-fg">{nameOf(current.contact)}</p>
                <p className="font-mono text-xs text-fg-3">{current.contact.ig_user_id}</p>
              </div>
            </div>
            <div className="flex-1 space-y-4 overflow-y-auto p-5">
              {current.messages.map((m) => {
                const out = m.direction === "out";
                return (
                  <div key={m.id} className={cx("flex", out ? "justify-end" : "justify-start")}>
                    <div className="max-w-[70%]">
                      <div
                        className={cx(
                          "whitespace-pre-wrap break-words rounded-panel px-4 py-2.5 text-sm",
                          out
                            ? "rounded-br-sm bg-fg text-on-fg"
                            : "rounded-bl-sm bg-raised text-fg"
                        )}
                      >
                        {m.text}
                      </div>
                      <span
                        className={cx(
                          "mt-1 block font-mono text-xs text-fg-3",
                          out ? "text-right" : "text-left"
                        )}
                      >
                        {formatTime(m.created_at)} · via {sourceLabel(m.source)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center text-sm text-fg-3">
            Selecione uma conversa
          </div>
        )}
      </div>
    </Card>
  );
}

export default function ConversasPage() {
  return (
    <AppShell title="Conversas" fill>
      <Suspense fallback={null}>
        <Conversas />
      </Suspense>
    </AppShell>
  );
}
