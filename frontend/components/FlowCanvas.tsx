"use client";

import { useCallback, useEffect, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  Panel,
  useNodesState,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Plus } from "lucide-react";
import { Button, KeywordTokens, cx } from "@/components/ui";
import type { EditorMessage } from "@/lib/flowGraph";

/** Máximo de mensagens no flow: mensagem 1 + 5 seguintes. */
export const MAX_MESSAGES = 6;

const NODE_W = 260;
const TRIGGER_H = 76;
const MSG_H = 84;
const GAP = 28;
const msgY = (i: number) => TRIGGER_H + GAP + i * (MSG_H + GAP);

type TriggerData = { label: string; keywords: string };
type MsgData = { index: number; text: string; buttons: number; selected: boolean; draggable: boolean };

const handleProps = (
  id: string,
  type: "source" | "target",
  position: Position,
  y: number
) => ({ id, type, position, x: NODE_W / 2 - 4, y, width: 8, height: 8 });

/** Nó do gatilho (topo do flow, fixo). */
function TriggerNode({ data }: NodeProps) {
  const d = data as unknown as TriggerData;
  return (
    <div className="flex h-full w-full flex-col justify-center gap-1.5 overflow-hidden rounded-card border border-line bg-card px-4">
      <p className="text-[13px] font-medium text-fg">Gatilho</p>
      <p className="truncate text-[13px] text-fg-2">{d.label}</p>
      {d.keywords && <KeywordTokens value={d.keywords} className="max-h-5 overflow-hidden" />}
      <Handle id="out" type="source" position={Position.Bottom} />
    </div>
  );
}

/** Nó de mensagem compacto: a edição acontece no inspetor abaixo do canvas. */
function MessageNode({ data }: NodeProps) {
  const d = data as unknown as MsgData;
  return (
    <div
      className={cx(
        "flex h-full w-full flex-col gap-1 overflow-hidden rounded-card border px-4 py-2.5",
        "transition-colors duration-150 ease-out",
        d.draggable ? "cursor-pointer" : "cursor-default",
        d.selected ? "border-line-strong bg-raised" : "border-line bg-card hover:border-line-strong"
      )}
    >
      <Handle id="in" type="target" position={Position.Top} />
      <p className="text-[13px] font-medium text-fg">Mensagem {d.index + 1}</p>
      <p
        className={cx(
          "line-clamp-2 text-[13px] leading-[18px]",
          d.text.trim() ? "text-fg-2" : "text-fg-3"
        )}
      >
        {d.text.trim() || "Sem texto"}
      </p>
      {d.buttons > 0 && (
        <p className="font-mono text-xs text-fg-3">
          {d.buttons} {d.buttons === 1 ? "botão" : "botões"}
        </p>
      )}
      <Handle id="out" type="source" position={Position.Bottom} />
    </div>
  );
}

const nodeTypes = { trigger: TriggerNode, message: MessageNode };

export default function FlowCanvas({
  messages,
  selectedId,
  triggerLabel,
  triggerKeywords,
  readOnly = false,
  onSelect,
  onReorder,
  onAdd,
}: {
  messages: EditorMessage[];
  selectedId: string | null;
  triggerLabel: string;
  /** Palavras-chave do gatilho ("preço, valor") para mostrar como tokens. */
  triggerKeywords?: string;
  /** Só visualização: sem selecionar, adicionar nem reordenar. */
  readOnly?: boolean;
  onSelect: (id: string) => void;
  /** Nova ordem dos ids das mensagens. */
  onReorder: (ids: string[]) => void;
  onAdd: () => void;
}) {
  // Dimensões e handles explícitos: o React Flow desenha as arestas sem
  // depender da medição por ResizeObserver (que não popula `measured`/
  // `handleBounds` neste ambiente — @xyflow/react 12 + React 19).
  const built = useMemo<Node[]>(() => {
    const nodes: Node[] = [
      {
        id: "trigger",
        type: "trigger",
        position: { x: 40, y: 0 },
        data: { label: triggerLabel, keywords: triggerKeywords ?? "" },
        draggable: false,
        selectable: false,
        width: NODE_W,
        height: TRIGGER_H,
        measured: { width: NODE_W, height: TRIGGER_H },
        handles: [handleProps("out", "source", Position.Bottom, TRIGGER_H - 4)],
      },
    ];
    messages.forEach((m, i) => {
      nodes.push({
        id: m.id,
        type: "message",
        position: { x: 40, y: msgY(i) },
        data: {
          index: i,
          text: m.text,
          buttons: m.buttons.length,
          selected: m.id === selectedId,
          draggable: !readOnly,
        },
        draggable: !readOnly,
        selectable: false,
        width: NODE_W,
        height: MSG_H,
        measured: { width: NODE_W, height: MSG_H },
        handles: [
          handleProps("in", "target", Position.Top, -4),
          handleProps("out", "source", Position.Bottom, MSG_H - 4),
        ],
      });
    });
    return nodes;
  }, [messages, selectedId, triggerLabel, triggerKeywords, readOnly]);

  const edges = useMemo<Edge[]>(() => {
    const ids = ["trigger", ...messages.map((m) => m.id)];
    return ids.slice(1).map((target, i) => ({
      id: `e-${ids[i]}-${target}`,
      source: ids[i],
      sourceHandle: "out",
      target,
      targetHandle: "in",
    }));
  }, [messages]);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>(built);
  useEffect(() => setNodes(built), [built, setNodes]);

  // Ao soltar um nó, reordena pela posição vertical e re-alinha na coluna.
  const onNodeDragStop = useCallback(() => {
    const ids = nodes
      .filter((n) => n.type === "message")
      .slice()
      .sort((a, b) => a.position.y - b.position.y)
      .map((n) => n.id);
    const changed = ids.some((id, i) => id !== messages[i]?.id);
    if (changed) onReorder(ids);
    else setNodes(built); // re-snap
  }, [nodes, messages, onReorder, built, setNodes]);

  return (
    <div className="octus-flow h-[420px] w-full overflow-hidden rounded-card border border-line bg-bg">
      <ReactFlow
        // Reenquadra ao mudar a quantidade de mensagens.
        key={messages.length}
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onNodeClick={(_, n) => !readOnly && n.type === "message" && onSelect(n.id)}
        onNodeDragStop={onNodeDragStop}
        nodeTypes={nodeTypes}
        nodesConnectable={false}
        elementsSelectable={false}
        colorMode="dark"
        fitView
        fitViewOptions={{ padding: 0.1, minZoom: 0.8, maxZoom: 1 }}
        panOnScroll
        zoomOnScroll={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} size={1} />
        <Controls showInteractive={false} />
        {!readOnly && (
          <Panel position="top-right">
            <Button
              variant="secondary"
              size="sm"
              icon={Plus}
              onClick={onAdd}
              disabled={messages.length >= MAX_MESSAGES}
            >
              Adicionar mensagem
            </Button>
          </Panel>
        )}
      </ReactFlow>
    </div>
  );
}
