"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Trash2, Workflow } from "lucide-react";
import AppShell from "@/components/AppShell";
import {
  Button,
  Card,
  EmptyState,
  IconButton,
  KeywordTokens,
  Note,
  SkeletonRows,
  Toggle,
  cx,
  useFeedback,
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
  const { toast, confirm } = useFeedback();
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
      if (!res.ok) throw new Error();
      setItems((prev) => prev.map((x) => (x.id === a.id ? { ...x, enabled: !x.enabled } : x)));
      toast(a.enabled ? "Automação pausada" : "Automação ativada");
    } catch {
      toast("Não foi possível alterar a automação. Tente de novo", "error");
    } finally {
      setBusy(null);
    }
  }

  async function remove(a: Automation) {
    const ok = await confirm({
      title: `Excluir "${a.name || "Sem nome"}"?`,
      description: "A automação para de responder e o histórico dela não pode ser recuperado",
      confirmLabel: "Excluir",
      tone: "danger",
    });
    if (!ok) return;
    setBusy(a.id);
    try {
      const res = await fetch(`/api/backend/automations/${a.id}`, { method: "DELETE" });
      if (!res.ok) throw new Error();
      setItems((prev) => prev.filter((x) => x.id !== a.id));
      toast("Automação excluída");
    } catch {
      toast("Não foi possível excluir a automação. Tente de novo", "error");
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
        <Card padding="none">
          <SkeletonRows rows={4} avatar={false} />
        </Card>
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
          {/* Cabeçalho das colunas: mesmas larguras das linhas, só onde elas aparecem */}
          <div className="hidden h-9 items-center gap-x-6 border-b border-line px-4 text-xs text-fg-3 md:flex">
            <span className="min-w-[220px] flex-1">Automação</span>
            <span className="hidden w-44 lg:block">Publicação</span>
            <span className="w-24">Conteúdo</span>
            <span className="w-28">Status</span>
            <span className="w-8" aria-hidden />
          </div>
          <ul>
            {items.map((a) => {
              const n = messageCount(a);
              return (
                <li
                  key={a.id}
                  className={cx(
                    "relative flex min-h-16 flex-wrap items-center gap-x-6 gap-y-2 border-b border-line px-4 py-3 last:border-b-0",
                    "transition-colors duration-150 ease-out hover:bg-raised/40",
                    busy === a.id && "opacity-50"
                  )}
                >
                  <div className="min-w-[220px] flex-1">
                    {/* Link esticado: a linha inteira abre o editor; toggle e excluir ficam acima (z-10) */}
                    <Link
                      href={`/automations/${a.id}/edit`}
                      className="block truncate rounded-sm text-sm font-medium text-fg after:absolute after:inset-0 after:content-['']"
                    >
                      {a.name || "Sem nome"}
                    </Link>
                    <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-fg-2">
                      {TRIGGER_TEXT[a.trigger]}
                      {hasKeyword(a) && <KeywordTokens value={a.keyword} />}
                    </p>
                  </div>

                  <p className="hidden w-44 text-[13px] text-fg-2 lg:block">{scopeText(a)}</p>

                  <p className="hidden w-24 font-mono text-xs text-fg-3 md:block">
                    {n} {n === 1 ? "mensagem" : "mensagens"}
                  </p>

                  <div className="relative z-10 flex w-28 items-center gap-2">
                    <Toggle
                      checked={a.enabled}
                      onChange={() => toggleEnabled(a)}
                      disabled={busy === a.id}
                      aria-label={a.enabled ? "Pausar automação" : "Ativar automação"}
                    />
                    <span className="text-[13px] text-fg-2">{a.enabled ? "Ativa" : "Pausada"}</span>
                  </div>

                  <IconButton
                    icon={Trash2}
                    tone="danger"
                    aria-label={`Excluir ${a.name || "automação sem nome"}`}
                    onClick={() => remove(a)}
                    disabled={busy === a.id}
                    className="relative z-10"
                  />
                </li>
              );
            })}
          </ul>
        </Card>
      )}
    </AppShell>
  );
}
