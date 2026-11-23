"use client";

import { createContext, useContext } from "react";

/** Estado e ações do editor que os nós e as arestas precisam (sem passar por `data`). */
export type FlowUi = {
  selectedId: string | null;
  /** Nós com erro de validação (ganham contorno `negative`). */
  errorIds: Set<string>;
  /** Saídas já ligadas: `nó|branch`. */
  used: Set<string>;
  canAddNode: boolean;
  hoveredEdgeId: string | null;
  selectedEdgeId: string | null;
  startId: string;
  /** Nó destacado de fora (ex.: onde uma execução parou). */
  highlightId: string | null;
  /** Abre o menu "+" ancorado na saída (o menu vive fora do nó, por causa do empilhamento). */
  openAddMenu: (nodeId: string, branch: string | null, anchor: DOMRect) => void;
  deleteEdge: (edgeId: string) => void;
};

const Ctx = createContext<FlowUi | null>(null);
export const FlowUiProvider = Ctx.Provider;

export function useFlowUi(): FlowUi {
  const v = useContext(Ctx);
  if (!v) throw new Error("useFlowUi precisa de <FlowUiProvider>");
  return v;
}
