"use client";

import { useEffect, useState } from "react";
import { MessageCircle } from "lucide-react";
import AppShell from "@/components/AppShell";
import Avatar from "@/components/Avatar";
import { useAccount } from "@/lib/account";

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

export default function ConversasPage() {
  const { accountId, resolved } = useAccount();
  const [convos, setConvos] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

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
        if (data.length) setSelected(data[0].contact.id);
      })
      .catch(() => setConvos([]))
      .finally(() => setLoading(false));
  }, [accountId, resolved]);

  const current = convos.find((c) => c.contact.id === selected);
  const nameOf = (c: Contact) => (c.username ? `@${c.username}` : `usuário ${c.ig_user_id}`);

  if (!loading && convos.length === 0) {
    return (
      <AppShell title="Conversas">
        <EmptyState />
      </AppShell>
    );
  }

  return (
    <AppShell title="Conversas">
      <div className="glass grid h-[calc(100vh-9rem)] grid-cols-[280px_1fr] overflow-hidden">
        {/* Lista de contatos */}
        <div className="overflow-y-auto border-r border-[var(--border)]">
          {convos.map((c) => {
            const last = c.messages[c.messages.length - 1];
            const active = c.contact.id === selected;
            return (
              <button
                key={c.contact.id}
                onClick={() => setSelected(c.contact.id)}
                className={`flex w-full items-center gap-3 border-b border-[var(--border)] px-4 py-3 text-left transition-colors ${
                  active ? "bg-[var(--gold)]/10" : "hover:bg-white/5"
                }`}
              >
                <Avatar src={c.contact.profile_pic} name={nameOf(c.contact)} size={38} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{nameOf(c.contact)}</p>
                  <p className="truncate text-xs text-[var(--muted)]">
                    {last ? (last.direction === "out" ? "Você: " : "") + last.text : ""}
                  </p>
                </div>
              </button>
            );
          })}
        </div>

        {/* Mensagens da conversa */}
        <div className="flex flex-col">
          {current ? (
            <>
              <div className="flex items-center gap-3 border-b border-[var(--border)] px-5 py-3">
                <Avatar src={current.contact.profile_pic} name={nameOf(current.contact)} size={40} />
                <div>
                  <p className="font-semibold leading-tight">{nameOf(current.contact)}</p>
                  <p className="mono text-xs text-[var(--muted)]">
                    IGSID: {current.contact.ig_user_id}
                  </p>
                </div>
              </div>
              <div className="flex-1 space-y-4 overflow-y-auto p-5">
                {current.messages.map((m) => {
                  const out = m.direction === "out";
                  return (
                    <div key={m.id} className={`flex ${out ? "justify-end" : "justify-start"}`}>
                      <div className="max-w-[72%]">
                        <div
                          className={`whitespace-pre-wrap break-words px-4 py-2.5 text-sm shadow-sm ${
                            out
                              ? "rounded-2xl rounded-br-md bg-[var(--gold)] text-[#2a1e05]"
                              : "rounded-2xl rounded-bl-md border border-[var(--border)] bg-neutral-800 text-[var(--fg)]"
                          }`}
                        >
                          {m.text}
                        </div>
                        <span
                          className={`mono mt-1 block text-[10px] text-[var(--muted)] ${
                            out ? "text-right" : "text-left"
                          }`}
                        >
                          {out ? "enviada" : "recebida"} ·{" "}
                          {new Date(m.created_at).toLocaleString("pt-BR")}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center text-sm text-[var(--muted)]">
              Selecione uma conversa
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}

function EmptyState() {
  return (
    <div className="glass flex flex-col items-center justify-center px-6 py-20 text-center">
      <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--gold)]/10 text-[var(--gold)]">
        <MessageCircle size={26} />
      </span>
      <h3 className="text-lg font-semibold">Nenhuma conversa ainda</h3>
      <p className="mt-1 max-w-sm text-sm text-[var(--muted)]">
        Quando suas automações dispararem DMs e as pessoas responderem, as conversas
        aparecem aqui. Conecte o Instagram para começar.
      </p>
    </div>
  );
}
