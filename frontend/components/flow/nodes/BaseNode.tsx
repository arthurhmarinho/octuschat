"use client";

import { Handle, Position } from "@xyflow/react";
import { Plus, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "@/components/ui";
import { INPUT_Y, NODE_W, metaOf, nodeHeight, outputsOf, type GraphNode } from "@/lib/flowGraph";
import { NODE_LABEL } from "@/lib/flowGraph";
import { useFlowUi } from "./context";

/**
 * Casca comum de todos os nós: cabeçalho (ícone + tipo), corpo de 2 linhas,
 * meta em mono e as saídas nomeadas no rodapé, cada uma com o seu handle.
 * As alturas são fixas e iguais às de `lib/flowGraph.ts` (o canvas não mede o DOM).
 */
export default function BaseNode({
  node,
  icon: Icon,
  body,
  muted,
}: {
  node: GraphNode;
  icon: LucideIcon;
  body: ReactNode;
  /** Corpo vazio/placeholder (cinza mais apagado). */
  muted?: boolean;
}) {
  const ui = useFlowUi();
  const selected = ui.selectedId === node.id;
  const hasError = ui.errorIds.has(node.id);
  const meta = metaOf(node);

  return (
    <div
      style={{ width: NODE_W, height: nodeHeight(node) }}
      className={cx(
        "relative overflow-visible rounded-card border px-3 pt-3",
        "transition-[background-color,border-color] duration-150 ease-out",
        hasError ? "border-negative/70" : selected ? "border-line-strong" : "border-line hover:border-line-strong",
        selected ? "bg-raised" : "bg-card",
        ui.highlightId === node.id && "ring-2 ring-fg/40"
      )}
    >
      <Handle
        id="in"
        type="target"
        position={Position.Left}
        style={{ top: INPUT_Y }}
        className="!h-2 !w-2"
      />

      <div className="flex h-5 items-center gap-2">
        <Icon size={16} strokeWidth={1.5} className="shrink-0 text-fg-3" />
        <span className="text-[13px] font-medium text-fg">{NODE_LABEL[node.type]}</span>
        {ui.startId === node.id && <span className="ml-auto font-mono text-xs text-fg-3">início</span>}
      </div>

      <p
        className={cx(
          "mt-2 line-clamp-2 h-9 break-words text-[13px] leading-[18px]",
          muted ? "text-fg-3" : "text-fg-2"
        )}
      >
        {body}
      </p>

      {meta && <p className="mt-2 h-4 truncate font-mono text-xs leading-4 text-fg-3">{meta}</p>}

      <div className="-mx-3 mt-2">
        {outputsOf(node).map((o) => {
          const connected = ui.used.has(`${node.id}|${o.branch ?? ""}`);
          return (
            <div key={o.handle} className="relative flex h-7 items-center justify-between px-3">
              <span className="truncate text-xs text-fg-3">{o.label}</span>
              {!connected && (
                <button
                  type="button"
                  aria-label={`Adicionar nó depois de ${o.label}`}
                  disabled={!ui.canAddNode}
                  onClick={(e) => ui.openAddMenu(node.id, o.branch, e.currentTarget.getBoundingClientRect())}
                  className="nodrag nopan mr-3 inline-flex h-5 w-5 items-center justify-center rounded-control border border-line text-fg-3 transition-colors duration-150 ease-out hover:border-line-strong hover:text-fg disabled:opacity-40"
                >
                  <Plus size={12} strokeWidth={1.5} />
                </button>
              )}
              <Handle id={o.handle} type="source" position={Position.Right} className="!h-2 !w-2" />
            </div>
          );
        })}
      </div>
    </div>
  );
}
