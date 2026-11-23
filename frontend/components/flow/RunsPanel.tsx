"use client";

import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Avatar from "@/components/Avatar";
import { EmptyState, IconButton, Note, SkeletonRows, StatusDot, cx } from "@/components/ui";
import { formatDateTime, formatRelative } from "@/lib/format";
import { NODE_LABEL, nodeById, type FlowGraph } from "@/lib/flowGraph";
import { History } from "lucide-react";

type Run = {
  id: number;
  contact: { username: string | null; profile_pic: string | null };
  status: "running" | "waiting" | "completed" | "expired" | "failed" | "cancelled";
  current_node_id: string | null;
  waiting_for: "reply" | "timer" | null;
  resume_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
  vars: Record<string, string>;
};

const STATUS: Record<Run["status"], { label: string; tone: "positive" | "neutral" | "negative" }> = {
  running: { label: "Em andamento", tone: "neutral" },
  waiting: { label: "Esperando", tone: "neutral" },
  completed: { label: "Concluída", tone: "positive" },
  expired: { label: "Expirada", tone: "neutral" },
  failed: { label: "Falhou", tone: "negative" },
  cancelled: { label: "Cancelada", tone: "neutral" },
};

/** Motivo gravado pelo backend → texto humano. */
function humanError(code: string | null): string | null {
  if (!code) return null;
  if (code === "outside_window") return "Janela de 24 h fechada";
  if (code === "quick_replies_unsupported_in_private_reply")
    return "A Meta não aceitou respostas rápidas na resposta privada; foi enviado só o texto";
  if (code === "automation_disabled") return "Automação desativada";
  if (code === "account_or_contact_missing") return "Conta ou contato removido";
  return code;
}

function nodeName(graph: FlowGraph, id: string | null): string {
  if (!id) return "—";
  const n = nodeById(graph, id);
  if (!n) return "nó removido";
  const text = "text" in n ? (n.text ?? "").trim() : "";
  return text ? `${NODE_LABEL[n.type]} · ${text.length > 28 ? `${text.slice(0, 28)}…` : text}` : NODE_LABEL[n.type];
}

/**
 * Aba Execuções: onde cada contato parou neste fluxo. Só leitura. Clicar numa
 * execução destaca o nó no canvas e mostra as respostas coletadas.
 */
export default function RunsPanel({
  automationId,
  graph,
  selectedRunId,
  onSelect,
}: {
  automationId: number;
  graph: FlowGraph;
  selectedRunId: number | null;
  onSelect: (run: Run | null) => void;
}) {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState(false);

  const load = useCallback(() => {
    setError(false);
    fetch(`/api/backend/automations/${automationId}/runs?limit=50`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: Run[]) => setRuns(data))
      .catch(() => setError(true));
  }, [automationId]);

  useEffect(() => load(), [load]);

  if (error) {
    return (
      <Note variant="warning">Não foi possível carregar as execuções. Tente de novo em instantes</Note>
    );
  }
  if (!runs) return <SkeletonRows rows={4} />;

  return (
    <div className="-mx-1">
      <div className="mb-2 flex items-center justify-between px-1">
        <p className="text-[13px] text-fg-2">
          {runs.length === 0 ? "Nenhuma execução ainda" : `${runs.length} ${runs.length === 1 ? "execução" : "execuções"} recentes`}
        </p>
        <IconButton icon={RefreshCw} aria-label="Atualizar execuções" onClick={load} />
      </div>

      {runs.length === 0 ? (
        <EmptyState
          icon={History}
          title="Nenhum contato passou por aqui"
          description="Quando o gatilho disparar, cada contato aparece nesta lista"
        />
      ) : (
        <ul className="divide-y divide-line">
          {runs.map((r) => {
            const st = STATUS[r.status];
            const active = r.id === selectedRunId;
            const reason = humanError(r.last_error);
            const waiting = r.status === "waiting" || r.status === "running";
            return (
              <li key={r.id}>
                <button
                  type="button"
                  aria-pressed={active}
                  onClick={() => onSelect(active ? null : r)}
                  className={cx(
                    "w-full rounded-control px-1 py-3 text-left transition-colors duration-150 ease-out",
                    active ? "bg-raised" : "hover:bg-raised/50"
                  )}
                >
                  <div className="flex items-center gap-2.5">
                    <Avatar src={r.contact.profile_pic} name={r.contact.username ?? "?"} size={28} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-fg">
                        {r.contact.username ? `@${r.contact.username}` : "Contato"}
                      </p>
                      <p className="flex items-center gap-1.5 text-xs text-fg-2">
                        <StatusDot tone={st.tone} />
                        {st.label}
                        {waiting && r.waiting_for === "reply" && " resposta"}
                        {waiting && r.waiting_for === "timer" && " o prazo"}
                      </p>
                    </div>
                    <span className="shrink-0 font-mono text-xs text-fg-3">{formatRelative(r.updated_at)}</span>
                  </div>
                  <p className="mt-1.5 truncate pl-[38px] text-xs text-fg-3">
                    Parou em: {nodeName(graph, r.current_node_id)}
                  </p>
                  {reason && <p className="mt-1 pl-[38px] text-xs text-fg-2">{reason}</p>}
                  {r.status === "waiting" && r.resume_at && (
                    <p className="mt-1 pl-[38px] font-mono text-xs text-fg-3">até {formatDateTime(r.resume_at)}</p>
                  )}
                  {active && Object.keys(r.vars).length > 0 && (
                    <dl className="mt-2 space-y-1 pl-[38px]">
                      {Object.entries(r.vars).map(([k, v]) => (
                        <div key={k} className="flex gap-2 text-xs">
                          <dt className="font-mono text-fg-3">{`{{${k}}}`}</dt>
                          <dd className="min-w-0 break-words text-fg">{v}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
