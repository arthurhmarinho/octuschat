"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Workflow, KeyRound, MessageSquareReply, MessageCircle, Pencil, Trash2 } from "lucide-react";
import AppShell from "@/components/AppShell";
import { useAccount } from "@/lib/account";

type Trigger = "comment_any" | "comment_keyword" | "dm_keyword" | "dm_any";
type Automation = {
  id: number;
  name: string;
  trigger: Trigger;
  keyword: string | null;
  reply_message: string;
  enabled: boolean;
};

const TRIGGER_LABEL: Record<Trigger, string> = {
  comment_keyword: "comentário",
  comment_any: "qualquer comentário",
  dm_keyword: "DM",
  dm_any: "qualquer DM (padrão)",
};

type LoadState = "loading" | "ready" | "error";

export default function AutomationsPage() {
  const { accountId, resolved } = useAccount();
  const [items, setItems] = useState<Automation[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [busy, setBusy] = useState<number | null>(null);

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

  async function toggleEnabled(a: Automation) {
    setBusy(a.id);
    try {
      const res = await fetch(`/api/backend/automations/${a.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !a.enabled }),
      });
      if (res.ok) {
        setItems((prev) =>
          prev.map((x) => (x.id === a.id ? { ...x, enabled: !x.enabled } : x))
        );
      }
    } finally {
      setBusy(null);
    }
  }

  async function remove(a: Automation) {
    if (!confirm(`Excluir a automação "${a.name || "Sem nome"}"? Isso não pode ser desfeito.`))
      return;
    setBusy(a.id);
    try {
      const res = await fetch(`/api/backend/automations/${a.id}`, { method: "DELETE" });
      if (res.ok) setItems((prev) => prev.filter((x) => x.id !== a.id));
    } finally {
      setBusy(null);
    }
  }

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
            <div
              key={a.id}
              className={`flex items-center gap-4 px-5 py-4 ${busy === a.id ? "opacity-50" : ""}`}
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--gold)]/10 text-[var(--gold)]">
                {a.trigger.startsWith("dm") ? (
                  <MessageCircle size={16} />
                ) : a.keyword ? (
                  <KeyRound size={16} />
                ) : (
                  <MessageSquareReply size={16} />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{a.name || "Sem nome"}</p>
                <p className="mono truncate text-xs text-[var(--muted)]">
                  {a.keyword
                    ? `${TRIGGER_LABEL[a.trigger]}: "${a.keyword}"`
                    : TRIGGER_LABEL[a.trigger]}
                </p>
              </div>

              {/* Toggle ativar/desativar */}
              <button
                type="button"
                onClick={() => toggleEnabled(a)}
                disabled={busy === a.id}
                title={a.enabled ? "Desativar" : "Ativar"}
                className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${
                  a.enabled ? "bg-[var(--green)]" : "bg-white/15"
                }`}
              >
                <span
                  className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${
                    a.enabled ? "left-[18px]" : "left-0.5"
                  }`}
                />
              </button>

              <span className="mono w-14 text-center text-[10px] text-[var(--muted)]">
                {a.enabled ? "ativa" : "pausada"}
              </span>

              {/* Ações */}
              <Link
                href={`/automations/${a.id}/edit`}
                title="Editar"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--muted)] hover:bg-white/5 hover:text-white"
              >
                <Pencil size={15} />
              </Link>
              <button
                type="button"
                onClick={() => remove(a)}
                disabled={busy === a.id}
                title="Excluir"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--muted)] hover:bg-red-500/10 hover:text-red-400"
              >
                <Trash2 size={15} />
              </button>
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
