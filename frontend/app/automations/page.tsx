"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Pencil, Plus, Trash2, Workflow } from "lucide-react";
import AppShell from "@/components/AppShell";
import {
  Button,
  Card,
  EmptyState,
  IconButton,
  KeywordTokens,
  Note,
  Spinner,
  Toggle,
  cx,
} from "@/components/ui";
import { useAccount } from "@/lib/account";
import { TRIGGER_TEXT, type Trigger } from "@/lib/automation";

type Automation = {
  id: number;
  name: string;
  trigger: Trigger;
  keyword: string | null;
  enabled: boolean;
  post_id: string | null;
  bind_next: boolean;
  graph?: { nodes?: { type?: string }[] } | null;
};

type LoadState = "loading" | "ready" | "error";

const isComment = (t: Trigger) => t === "comment_any" || t === "comment_keyword";
const hasKeyword = (a: Automation) =>
  !!a.keyword && (a.trigger === "comment_keyword" || a.trigger === "dm_keyword" || a.trigger === "story_reply");

function scopeText(a: Automation): string {
  if (!isComment(a.trigger)) return "—";
  if (a.post_id) return "Publicação específica";
  if (a.bind_next) return "Próxima publicação";
  return "Todas as publicações";
}

function messageCount(a: Automation): number {
  const nodes = a.graph?.nodes ?? [];
  return nodes.filter((n) => (n.type ?? "message") === "message").length;
}

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
        setItems((prev) => prev.map((x) => (x.id === a.id ? { ...x, enabled: !x.enabled } : x)));
      }
    } finally {
      setBusy(null);
    }
  }

  async function remove(a: Automation) {
    if (!confirm(`Excluir a automação "${a.name || "Sem nome"}"? Isso não pode ser desfeito.`)) return;
    setBusy(a.id);
    try {
      const res = await fetch(`/api/backend/automations/${a.id}`, { method: "DELETE" });
      if (res.ok) setItems((prev) => prev.filter((x) => x.id !== a.id));
    } finally {
      setBusy(null);
    }
  }

  const newButton = (
    <Button variant="primary" size="sm" icon={Plus} href="/automations/new">
      Nova automação
    </Button>
  );

  return (
    <AppShell title="Automações" action={newButton}>
      {state === "loading" && (
        <div className="flex justify-center py-24">
          <Spinner />
        </div>
      )}

      {state === "error" && (
        <Note variant="warning">
          Não foi possível carregar suas automações. Verifique a conexão e tente de novo
        </Note>
      )}

      {state === "ready" && items.length === 0 && (
        <Card padding="none">
          <EmptyState
            icon={Workflow}
            title="Nenhuma automação"
            description="Responda comentários e DMs automaticamente"
            action={
              <Button variant="secondary" href="/automations/new">
                Nova automação
              </Button>
            }
          />
        </Card>
      )}

      {state === "ready" && items.length > 0 && (
        <Card padding="none">
          <ul>
            {items.map((a) => {
              const n = messageCount(a);
              return (
                <li
                  key={a.id}
                  className={cx(
                    "flex min-h-16 flex-wrap items-center gap-x-6 gap-y-2 border-b border-line px-4 py-3 last:border-b-0",
                    busy === a.id && "opacity-50"
                  )}
                >
                  <div className="min-w-[220px] flex-1">
                    <p className="truncate text-sm font-medium text-fg">{a.name || "Sem nome"}</p>
                    <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-fg-2">
                      {TRIGGER_TEXT[a.trigger]}
                      {hasKeyword(a) && <KeywordTokens value={a.keyword} />}
                    </p>
                  </div>

                  <p className="hidden w-44 text-[13px] text-fg-2 lg:block">{scopeText(a)}</p>

                  <p className="hidden w-24 font-mono text-xs text-fg-3 md:block">
                    {n} {n === 1 ? "mensagem" : "mensagens"}
                  </p>

                  <div className="flex w-28 items-center gap-2">
                    <Toggle
                      checked={a.enabled}
                      onChange={() => toggleEnabled(a)}
                      disabled={busy === a.id}
                      aria-label={a.enabled ? "Pausar automação" : "Ativar automação"}
                    />
                    <span className="text-[13px] text-fg-2">{a.enabled ? "Ativa" : "Pausada"}</span>
                  </div>

                  <div className="flex items-center gap-1">
                    <Link
                      href={`/automations/${a.id}/edit`}
                      aria-label="Editar"
                      className="inline-flex h-8 w-8 items-center justify-center rounded-control text-fg-3 transition-[background-color,color] duration-150 ease-out hover:bg-raised hover:text-fg"
                    >
                      <Pencil size={16} strokeWidth={1.5} />
                    </Link>
                    <IconButton
                      icon={Trash2}
                      tone="danger"
                      aria-label="Excluir"
                      onClick={() => remove(a)}
                      disabled={busy === a.id}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      )}
    </AppShell>
  );
}
