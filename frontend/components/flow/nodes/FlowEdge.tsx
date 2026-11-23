"use client";

import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from "@xyflow/react";
import { X } from "lucide-react";
import { cx } from "@/components/ui";
import { useFlowUi } from "./context";

/** Aresta com o "×" no meio (visível no hover ou selecionada). A do Gatilho não se apaga. */
export default function FlowEdge(props: EdgeProps) {
  const { id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, source } = props;
  const ui = useFlowUi();
  const [path, labelX, labelY] = getBezierPath({
    sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition,
  });
  const selected = ui.selectedEdgeId === id;
  const visible = (selected || ui.hoveredEdgeId === id) && source !== "trigger";

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        interactionWidth={20}
        style={{ stroke: selected ? "var(--fg)" : "var(--fg-3)", strokeWidth: 1.5 }}
      />
      {source !== "trigger" && (
        <EdgeLabelRenderer>
          <button
            type="button"
            aria-label="Apagar ligação"
            onClick={() => ui.deleteEdge(id)}
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
            className={cx(
              "nodrag nopan pointer-events-auto absolute flex h-5 w-5 items-center justify-center",
              "rounded-full border border-line-strong bg-raised text-fg-2",
              "transition-opacity duration-150 ease-out hover:text-fg",
              visible ? "opacity-100" : "pointer-events-none opacity-0 focus-visible:pointer-events-auto focus-visible:opacity-100"
            )}
          >
            <X size={12} strokeWidth={1.5} />
          </button>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
