"use client";

import { useCallback, useEffect, useRef } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  Panel,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Plus, X, Zap } from "lucide-react";

/** Máximo de mensagens no flow: mensagem 1 + 5 seguintes. */
const MAX_MESSAGES = 6;

type MsgData = {
  index: number;
  value: string;
  canDelete: boolean;
  onEdit: (i: number, v: string) => void;
  onDelete: (i: number) => void;
};

/** Nó do gatilho (topo do flow). */
function TriggerNode({ data }: NodeProps) {
  const label = (data as { label: string }).label;
  return (
    <div className="flex h-full w-[240px] flex-col justify-center rounded-xl border border-[var(--gold)]/50 bg-[var(--gold)]/10 px-4 py-3 shadow-lg">
      <div className="flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--gold)]/20 text-[var(--gold)]">
          <Zap size={15} />
        </span>
        <div className="min-w-0">
          <p className="mono text-[10px] uppercase tracking-wide text-[var(--gold)]">Gatilho</p>
          <p className="truncate text-sm font-medium text-white">{label}</p>
        </div>
      </div>
      <Handle id="out" type="source" position={Position.Bottom} className="!bg-[var(--gold)]" />
    </div>
  );
}

/** Nó de mensagem (editável inline). */
function MessageNode({ data }: NodeProps) {
  const d = data as unknown as MsgData;
  return (
    <div className="flex h-full w-[240px] flex-col rounded-xl border border-[var(--border)] bg-[#141414] shadow-lg">
      <Handle id="in" type="target" position={Position.Top} className="!bg-neutral-500" />
      <div className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
        <p className="mono text-[10px] uppercase tracking-wide text-[var(--muted)]">
          {d.index === 0 ? "Mensagem inicial" : `Mensagem ${d.index + 1}`}
        </p>
        {d.canDelete && (
          <button
            type="button"
            onClick={() => d.onDelete(d.index)}
            title="Remover mensagem"
            className="nodrag flex h-6 w-6 items-center justify-center rounded text-[var(--muted)] hover:bg-red-500/10 hover:text-red-400"
          >
            <X size={13} />
          </button>
        )}
      </div>
      <textarea
        defaultValue={d.value}
        onChange={(e) => d.onEdit(d.index, e.target.value)}
        placeholder={d.index === 0 ? "Oi! Obrigado pelo contato 💜" : `Mensagem ${d.index + 1}…`}
        className="nodrag nowheel w-full flex-1 resize-none rounded-b-xl bg-transparent px-3 py-2 text-sm text-white outline-none placeholder:text-neutral-600"
      />
      <Handle id="out" type="source" position={Position.Bottom} className="!bg-neutral-500" />
    </div>
  );
}

const nodeTypes = { trigger: TriggerNode, message: MessageNode };

export default function FlowCanvas({
  messages,
  triggerLabel,
  onMessagesChange,
}: {
  messages: string[];
  triggerLabel: string;
  onMessagesChange: (messages: string[]) => void;
}) {
  // Fonte de verdade interna do canvas (evita churn de identidade do array vindo
  // do pai). Inicializada uma vez; mudanças são empurradas para cima.
  const msgsRef = useRef<string[]>(messages.length ? messages : [""]);

  // Callbacks estáveis usados pelos nós.
  const onEditRef = useRef<(i: number, v: string) => void>(() => {});
  const onDeleteRef = useRef<(i: number) => void>(() => {});

  const buildNodes = useCallback(
    (msgs: string[], label: string): Node[] => {
      // Dimensões e handles explícitos: o React Flow desenha as arestas sem
      // depender da medição por ResizeObserver (que não popula `measured`/
      // `handleBounds` neste ambiente — @xyflow/react 12 + React 19).
      const TRIGGER_H = 66;
      const MSG_H = 128;
      const nodes: Node[] = [
        {
          id: "trigger",
          type: "trigger",
          position: { x: 40, y: 0 },
          data: { label },
          draggable: false,
          width: 240,
          height: TRIGGER_H,
          measured: { width: 240, height: TRIGGER_H },
          handles: [
            { id: "out", type: "source", position: Position.Bottom, x: 116, y: TRIGGER_H - 4, width: 8, height: 8 },
          ],
        },
      ];
      msgs.forEach((m, i) => {
        nodes.push({
          id: `msg-${i}`,
          type: "message",
          position: { x: 40, y: 110 + i * 170 },
          data: {
            index: i,
            value: m,
            canDelete: i > 0,
            onEdit: (idx: number, v: string) => onEditRef.current(idx, v),
            onDelete: (idx: number) => onDeleteRef.current(idx),
          },
          draggable: false,
          width: 240,
          height: MSG_H,
          measured: { width: 240, height: MSG_H },
          handles: [
            { id: "in", type: "target", position: Position.Top, x: 116, y: -4, width: 8, height: 8 },
            { id: "out", type: "source", position: Position.Bottom, x: 116, y: MSG_H - 4, width: 8, height: 8 },
          ],
        });
      });
      return nodes;
    },
    []
  );

  const buildEdges = useCallback((msgs: string[]): Edge[] => {
    const edges: Edge[] = [
      { id: "e-trigger", source: "trigger", sourceHandle: "out", target: "msg-0", targetHandle: "in", animated: true },
    ];
    for (let i = 1; i < msgs.length; i++) {
      edges.push({
        id: `e-${i}`,
        source: `msg-${i - 1}`,
        sourceHandle: "out",
        target: `msg-${i}`,
        targetHandle: "in",
        animated: true,
      });
    }
    return edges;
  }, []);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>(
    buildNodes(msgsRef.current, triggerLabel)
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(
    buildEdges(msgsRef.current)
  );

  const rebuild = useCallback(() => {
    setNodes(buildNodes(msgsRef.current, triggerLabel));
    setEdges(buildEdges(msgsRef.current));
  }, [buildNodes, buildEdges, triggerLabel, setNodes, setEdges]);

  // Edições de texto NÃO reconstroem a estrutura (preserva o foco do textarea);
  // apenas empurram o valor para o pai.
  onEditRef.current = (i: number, v: string) => {
    const next = [...msgsRef.current];
    next[i] = v;
    msgsRef.current = next;
    onMessagesChange(next);
  };
  onDeleteRef.current = (i: number) => {
    const next = msgsRef.current.filter((_, idx) => idx !== i);
    msgsRef.current = next.length ? next : [""];
    onMessagesChange(msgsRef.current);
    rebuild();
  };

  const onAdd = useCallback(() => {
    if (msgsRef.current.length >= MAX_MESSAGES) return;
    msgsRef.current = [...msgsRef.current, ""];
    onMessagesChange(msgsRef.current);
    rebuild();
  }, [onMessagesChange, rebuild]);

  // Atualiza o rótulo do gatilho quando ele muda no formulário.
  useEffect(() => {
    setNodes(buildNodes(msgsRef.current, triggerLabel));
  }, [triggerLabel, buildNodes, setNodes]);

  return (
    <div className="h-[440px] w-full overflow-hidden rounded-xl border border-[var(--border)] bg-black/40">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        colorMode="dark"
        fitView
        fitViewOptions={{ padding: 0.3 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={18} size={1} />
        <Controls showInteractive={false} />
        <Panel position="top-right">
          <button
            type="button"
            onClick={onAdd}
            disabled={msgsRef.current.length >= MAX_MESSAGES}
            className="btn-gold inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs disabled:opacity-40"
          >
            <Plus size={14} /> Adicionar mensagem
          </button>
        </Panel>
      </ReactFlow>
    </div>
  );
}
