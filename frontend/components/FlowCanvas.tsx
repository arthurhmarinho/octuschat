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
import { Plus, X, Zap, GripVertical } from "lucide-react";

/** Máximo de mensagens no flow: mensagem 1 + 5 seguintes. */
const MAX_MESSAGES = 6;

/** Mensagem com id estável — o id viaja com a mensagem ao reordenar (drag), o
 * que preserva o texto/foco do textarea (uncontrolled) mesmo mudando de posição. */
type Msg = { key: string; text: string };
const uid = () => Math.random().toString(36).slice(2, 9);
const toMsgs = (texts: string[]): Msg[] =>
  (texts.length ? texts : [""]).map((t) => ({ key: uid(), text: t }));

const TRIGGER_H = 66;
const MSG_H = 128;

type MsgData = {
  index: number;
  value: string;
  msgKey: string;
  canDelete: boolean;
  onEdit: (key: string, v: string) => void;
  onDelete: (key: string) => void;
};

/** Nó do gatilho (topo do flow, fixo). */
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

/** Nó de mensagem (editável inline, arrastável para reordenar). */
function MessageNode({ data }: NodeProps) {
  const d = data as unknown as MsgData;
  return (
    <div className="flex h-full w-[240px] flex-col rounded-xl border border-[var(--border)] bg-[#141414] shadow-lg">
      <Handle id="in" type="target" position={Position.Top} className="!bg-neutral-500" />
      <div className="flex cursor-grab items-center justify-between border-b border-[var(--border)] px-3 py-2 active:cursor-grabbing">
        <p className="mono flex items-center gap-1 text-[10px] uppercase tracking-wide text-[var(--muted)]">
          <GripVertical size={12} className="text-neutral-600" />
          {d.index === 0 ? "Mensagem inicial" : `Mensagem ${d.index + 1}`}
        </p>
        {d.canDelete && (
          <button
            type="button"
            onClick={() => d.onDelete(d.msgKey)}
            title="Remover mensagem"
            className="nodrag flex h-6 w-6 items-center justify-center rounded text-[var(--muted)] hover:bg-red-500/10 hover:text-red-400"
          >
            <X size={13} />
          </button>
        )}
      </div>
      <textarea
        defaultValue={d.value}
        onChange={(e) => d.onEdit(d.msgKey, e.target.value)}
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
  // Fonte de verdade interna (com ids estáveis). Inicializada uma vez; mudanças
  // são empurradas para o pai como string[].
  const msgsRef = useRef<Msg[]>(toMsgs(messages));

  // Callbacks estáveis usados pelos nós.
  const onEditRef = useRef<(key: string, v: string) => void>(() => {});
  const onDeleteRef = useRef<(key: string) => void>(() => {});

  const emit = useCallback(
    () => onMessagesChange(msgsRef.current.map((m) => m.text)),
    [onMessagesChange]
  );

  const buildNodes = useCallback((msgs: Msg[], label: string): Node[] => {
    // Dimensões e handles explícitos: o React Flow desenha as arestas sem
    // depender da medição por ResizeObserver (que não popula `measured`/
    // `handleBounds` neste ambiente — @xyflow/react 12 + React 19).
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
        id: `msg-${m.key}`,
        type: "message",
        position: { x: 40, y: 110 + i * 170 },
        data: {
          index: i,
          value: m.text,
          msgKey: m.key,
          canDelete: i > 0,
          onEdit: (key: string, v: string) => onEditRef.current(key, v),
          onDelete: (key: string) => onDeleteRef.current(key),
        },
        draggable: true,
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
  }, []);

  const buildEdges = useCallback((msgs: Msg[]): Edge[] => {
    if (!msgs.length) return [];
    const edges: Edge[] = [
      { id: "e-trigger", source: "trigger", sourceHandle: "out", target: `msg-${msgs[0].key}`, targetHandle: "in", animated: true },
    ];
    for (let i = 1; i < msgs.length; i++) {
      edges.push({
        id: `e-${msgs[i].key}`,
        source: `msg-${msgs[i - 1].key}`,
        sourceHandle: "out",
        target: `msg-${msgs[i].key}`,
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
  onEditRef.current = (key: string, v: string) => {
    const m = msgsRef.current.find((x) => x.key === key);
    if (m) {
      m.text = v;
      emit();
    }
  };
  onDeleteRef.current = (key: string) => {
    const next = msgsRef.current.filter((x) => x.key !== key);
    msgsRef.current = next.length ? next : toMsgs([""]);
    emit();
    rebuild();
  };

  const onAdd = useCallback(() => {
    if (msgsRef.current.length >= MAX_MESSAGES) return;
    msgsRef.current = [...msgsRef.current, { key: uid(), text: "" }];
    emit();
    rebuild();
  }, [emit, rebuild]);

  // Ao soltar um nó, reordena a sequência pela posição vertical e re-alinha.
  const onNodeDragStop = useCallback(() => {
    const orderedKeys = nodes
      .filter((n) => n.type === "message")
      .slice()
      .sort((a, b) => a.position.y - b.position.y)
      .map((n) => (n.data as unknown as MsgData).msgKey);
    const byKey = new Map(msgsRef.current.map((m) => [m.key, m]));
    const reordered = orderedKeys
      .map((k) => byKey.get(k))
      .filter((m): m is Msg => Boolean(m));
    if (reordered.length !== msgsRef.current.length) {
      rebuild(); // segurança: re-alinha se algo destoou
      return;
    }
    const changed = reordered.some((m, i) => m.key !== msgsRef.current[i].key);
    msgsRef.current = reordered;
    if (changed) emit();
    rebuild(); // re-snap para a coluna limpa na nova ordem
  }, [nodes, emit, rebuild]);

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
        onNodeDragStop={onNodeDragStop}
        nodeTypes={nodeTypes}
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
