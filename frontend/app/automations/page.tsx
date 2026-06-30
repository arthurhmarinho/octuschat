"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Workflow, KeyRound, MessageSquareReply } from "lucide-react";
import AppShell from "@/components/AppShell";
import { useAccount } from "@/lib/account";

type Automation = {
  id: number;
  name: string;
  trigger: "comment_any" | "comment_keyword";
  keyword: string | null;
  reply_message: string;
  enabled: boolean;
};

type LoadState = "loading" | "ready" | "error";

export default function AutomationsPage() {
  const { accountId, resolved } = useAccount();
  const [items, setItems] = useState<Automation[]>([]);
  const [state, setState] = useState<LoadState>("loading");

  useEffect(() => {
    if (!resolved) return;
    if (!accountId) {
      setState("ready");
      return;
    }
    fetch(`/api/backend/automations?account_id=${accountId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data) => {
        setItems(data);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, [accountId, resolved]);

  const newButton = (
    <Link href="/automations/new" className="btn-gold inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm">
      <Plus size={16} /> Nova automação
    </Link>
  );

  return (
    <AppShell title="Automações" action={newButton}>
      {state === "ready" && items.length > 0 ? (
        <div className="glass divide-y divide-[var(--border)] overflow-hidden">
          {items.map((a) => (
            <div key={a.id} className="flex items-center gap-4 px-5 py-4">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--gold)]/10 text-[var(--gold)]">
                {a.trigger === "comment_keyword" ? <KeyRound size={16} /> : <MessageSquareReply size={16} />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{a.name || "Sem nome"}</p>
                <p className="mono truncate text-xs text-[var(--muted)]">
                  {a.trigger === "comment_keyword"
                    ? `palavra-chave: "${a.keyword}"`
                    : "qualquer comentário"}
                </p>
              </div>
              <span
                className={`mono rounded border px-2 py-0.5 text-[10px] ${
                  a.enabled
                    ? "border-[var(--green)]/40 bg-[var(--green)]/10 text-[var(--green)]"
                    : "border-[var(--border)] bg-white/5 text-[var(--muted)]"
                }`}
              >
                {a.enabled ? "● ativa" : "pausada"}
              </span>
            </div>
          ))}
        </div>
      ) : (
        /* Estado vazio (também cobre backend offline) */
        <div className="glass flex flex-col items-center justify-center px-6 py-20 text-center">
          <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--gold)]/10 text-[var(--gold)]">
            <Workflow size={26} />
          </span>
          <h3 className="text-lg font-semibold">Nenhuma automação ainda</h3>
          <p className="mt-1 max-w-sm text-sm text-[var(--muted)]">
            {state === "error"
              ? "Não consegui carregar (backend offline). Você ainda pode criar e ver o preview."
              : "Crie sua primeira automação: comentário com palavra-chave → DM automática."}
          </p>
          <Link href="/automations/new" className="btn-gold mt-6 inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm">
            <Plus size={16} /> Criar automação
          </Link>
        </div>
      )}
    </AppShell>
  );
}
