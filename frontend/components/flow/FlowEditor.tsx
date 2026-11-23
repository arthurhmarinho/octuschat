"use client";

import {
  Background,
  Controls,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Connection,
  type Edge,
  type Node,
  type NodeChange,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { LayoutGrid, Redo2, Undo2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import DmPreview from "@/components/DmPreview";
import { Button, IconButton, Note, Segmented, cx, useFeedback } from "@/components/ui";
import {
  DEFAULT_HANDLE,
  INPUT_Y,
  MAX_NODES,
  NODE_LABEL,
  NODE_W,
  TRIGGER_H,
  TRIGGER_ID,
  branchOfHandle,
  handleOfBranch,
  makeNode,
  nodeById,
  nodeHeight,
  outputY,
  outputsOf,
  usedOutputs,
  wouldCycle,
  type FlowGraph,
  type GraphNode,
  type NodeType,
} from "@/lib/flowGraph";
import AddNodeMenu, { NODE_ICON, NODE_TYPES } from "./AddNodeMenu";
import NodeInspector from "./NodeInspector";
import FlowEdge from "./nodes/FlowEdge";
import { FlowUiProvider, type FlowUi } from "./nodes/context";
import { nodeTypes } from "./nodes/nodeTypes";
import { autoLayout } from "./layout";
import type { useFlowHistory } from "./useFlowHistory";
import type { Validation } from "./validateGraph";

export type FlowHistory = ReturnType<typeof useFlowHistory>;
type Tab = "edit" | "preview" | "runs";

const edgeTypes = { flow: FlowEdge };
const edgeId = (e: { source: string; branch?: string | null; target: string }) =>
  `e|${e.source}|${e.branch ?? ""}|${e.target}`;

const isEditable = (t: EventTarget | null) => {
  const el = t as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
};

function Canvas({
  flow,
  validation,
  triggerLabel,
  triggerKeywords,
  username,
  isComment,
  runsPanel,
  highlightId,
}: {
  flow: FlowHistory;
  validation: Validation;
  triggerLabel: string;
  triggerKeywords: string;
  username: string;
  isComment: boolean;
  /** Conteúdo da aba Execuções (só na edição de uma automação já salva). */
  runsPanel?: ReactNode;
  highlightId?: string | null;
}) {
  const { graph, update, transient, beginGesture, endGesture, undo, redo, canUndo, canRedo } = flow;
  const { toast } = useFeedback();
  const rf = useReactFlow();
  const wrapRef = useRef<HTMLDivElement>(null);

  const [selected, setSelected] = useState<string | null>(null); // id do nó, ou "trigger"
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("edit");
  const [menu, setMenu] = useState<{ nodeId: string; branch: string | null; anchor: DOMRect } | null>(null);
  const [organizing, setOrganizing] = useState(false);

  const canAddNode = graph.nodes.length < MAX_NODES;
  // Só vale na abertura (fitView lê as opções uma vez).
  const [initialFit] = useState(() => [
    { id: TRIGGER_ID },
    { id: graph.start },
    ...graph.edges.filter((e) => e.source === graph.start).map((e) => ({ id: e.target })),
  ]);
  const used = useMemo(() => usedOutputs(graph), [graph]);
  const errorIds = useMemo(
    () => new Set(validation.errors.map((i) => i.nodeId).filter((x): x is string => !!x)),
    [validation.errors]
  );

  // ── Nós e arestas do React Flow, derivados do grafo ──
  // Dimensões e handles explícitos: o React Flow não depende da medição por
  // ResizeObserver (que não popula `measured`/`handleBounds` em todo ambiente).
  const rfNodes = useMemo<Node[]>(() => {
    const startNode = nodeById(graph, graph.start);
    const trigger: Node = {
      id: TRIGGER_ID,
      type: "trigger",
      position: { x: (startNode?.position?.x ?? 340) - NODE_W - 80, y: startNode?.position?.y ?? 0 },
      data: { label: triggerLabel, keywords: triggerKeywords },
      draggable: false,
      selectable: false,
      deletable: false,
      width: NODE_W,
      height: TRIGGER_H,
      measured: { width: NODE_W, height: TRIGGER_H },
      handles: [
        { id: "out", type: "source", position: Position.Right, x: NODE_W - 4, y: TRIGGER_H / 2 - 4, width: 8, height: 8 },
      ],
    };
    const nodes = graph.nodes.map<Node>((n) => {
      const h = nodeHeight(n);
      return {
        id: n.id,
        type: n.type,
        position: n.position ?? { x: 0, y: 0 },
        data: { node: n },
        selectable: false,
        deletable: false,
        width: NODE_W,
        height: h,
        measured: { width: NODE_W, height: h },
        handles: [
          { id: "in", type: "target", position: Position.Left, x: -4, y: INPUT_Y - 4, width: 8, height: 8 },
          ...outputsOf(n).map((o, i) => ({
            id: o.handle,
            type: "source" as const,
            position: Position.Right,
            x: NODE_W - 4,
            y: outputY(n, i) - 4,
            width: 8,
            height: 8,
          })),
        ],
      };
    });
    return [trigger, ...nodes];
  }, [graph, triggerLabel, triggerKeywords]);

  const rfEdges = useMemo<Edge[]>(
    () => [
      { id: "e|trigger", source: TRIGGER_ID, sourceHandle: "out", target: graph.start, targetHandle: "in", type: "flow" },
      ...graph.edges.map<Edge>((e) => ({
        id: edgeId(e),
        source: e.source,
        sourceHandle: handleOfBranch(e.branch),
        target: e.target,
        targetHandle: "in",
        type: "flow",
      })),
    ],
    [graph]
  );

  // ── Edição ──
  const patchNode = useCallback(
    (id: string, patch: Partial<GraphNode>, key?: string) =>
      update(
        (g) => ({ ...g, nodes: g.nodes.map((n) => (n.id === id ? ({ ...n, ...patch } as GraphNode) : n)) }),
        key
      ),
    [update]
  );

  const addNode = useCallback(
    (type: NodeType, from?: { nodeId: string; branch: string | null }) => {
      if (graph.nodes.length >= MAX_NODES) return;
      let position: { x: number; y: number };
      if (from) {
        const src = nodeById(graph, from.nodeId);
        const idx = src ? Math.max(0, outputsOf(src).findIndex((o) => (o.branch ?? "") === (from.branch ?? ""))) : 0;
        position = {
          x: (src?.position?.x ?? 0) + NODE_W + 80,
          y: (src?.position?.y ?? 0) + idx * 56,
        };
      } else {
        const box = wrapRef.current?.getBoundingClientRect();
        const c = rf.screenToFlowPosition({
          x: (box?.left ?? 0) + (box?.width ?? 600) / 2,
          y: (box?.top ?? 0) + (box?.height ?? 400) / 2,
        });
        // Perto do centro, em degraus, para não empilhar nós novos no mesmo lugar.
        const step = graph.nodes.length % 6;
        position = { x: Math.round(c.x - NODE_W / 2 + step * 24), y: Math.round(c.y - 60 + step * 24) };
      }
      const node = makeNode(type, position);
      update((g) => ({
        ...g,
        nodes: [...g.nodes, node],
        edges: from
          ? [
              ...g.edges.filter((e) => !(e.source === from.nodeId && (e.branch ?? "") === (from.branch ?? ""))),
              { source: from.nodeId, target: node.id, ...(from.branch ? { branch: from.branch } : {}) },
            ]
          : g.edges,
      }));
      setSelected(node.id);
      setSelectedEdge(null);
      setTab("edit");
    },
    [graph, update, rf]
  );

  const deleteNode = useCallback(
    (id: string) => {
      if (id === TRIGGER_ID) return;
      let nextStart = graph.start;
      if (id === graph.start) {
        const out = graph.edges.filter((e) => e.source === id);
        const heir = out.map((e) => e.target).find((t) => graph.edges.filter((e) => e.target === t).length === 1);
        if (!heir) {
          toast("Ligue o Gatilho a outro nó antes de excluir o primeiro nó", "error");
          return;
        }
        nextStart = heir;
      }
      update((g) => ({
        ...g,
        start: nextStart,
        nodes: g.nodes.filter((n) => n.id !== id),
        edges: g.edges.filter((e) => e.source !== id && e.target !== id),
      }));
      setSelected(null);
    },
    [graph, update, toast]
  );

  const deleteEdge = useCallback(
    (id: string) => {
      if (id === "e|trigger") return;
      update((g) => ({ ...g, edges: g.edges.filter((e) => edgeId(e) !== id) }));
      setSelectedEdge(null);
    },
    [update]
  );

  const isValidConnection = useCallback(
    (c: Connection | Edge): boolean => {
      const { source, target, sourceHandle } = c;
      if (!source || !target || target === TRIGGER_ID || source === target) return false;
      if (source === TRIGGER_ID) return !graph.edges.some((e) => e.target === target); // trocar o início
      if (target === graph.start) return false;
      const src = nodeById(graph, source);
      if (!src || !outputsOf(src).some((o) => o.handle === (sourceHandle ?? DEFAULT_HANDLE))) return false;
      return !wouldCycle(graph, source, target);
    },
    [graph]
  );

  const onConnect = useCallback(
    (c: Connection) => {
      if (!isValidConnection(c)) return;
      if (c.source === TRIGGER_ID) {
        update((g) => ({ ...g, start: c.target }));
        return;
      }
      const branch = branchOfHandle(c.sourceHandle);
      update((g) => ({
        ...g,
        // Uma aresta por saída: ligar de novo substitui a anterior.
        edges: [
          ...g.edges.filter((e) => !(e.source === c.source && (e.branch ?? "") === (branch ?? ""))),
          { source: c.source, target: c.target, ...(branch ? { branch } : {}) },
        ],
      }));
    },
    [isValidConnection, update]
  );

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      const moves = changes.filter((c) => c.type === "position" && c.position);
      if (!moves.length) return;
      transient((g) => ({
        ...g,
        nodes: g.nodes.map((n) => {
          const m = moves.find((c) => c.type === "position" && c.id === n.id);
          return m && m.type === "position" && m.position ? { ...n, position: m.position } : n;
        }),
      }));
    },
    [transient]
  );

  const organize = useCallback(async () => {
    setOrganizing(true);
    try {
      const next = await autoLayout(graph);
      update(() => next);
      requestAnimationFrame(() => rf.fitView({ padding: 0.15, duration: 250 }));
    } catch {
      toast("Não foi possível organizar o fluxo", "error");
    } finally {
      setOrganizing(false);
    }
  }, [graph, update, rf, toast]);

  // ── Teclado: desfazer/refazer e apagar ──
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isEditable(e.target)) return;
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === "z") {
        e.preventDefault();
        e.shiftKey ? redo() : undo();
      } else if (mod && e.key.toLowerCase() === "y") {
        e.preventDefault();
        redo();
      } else if (e.key === "Backspace" || e.key === "Delete") {
        if (selectedEdge) deleteEdge(selectedEdge);
        else if (selected && selected !== TRIGGER_ID) deleteNode(selected);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo, redo, selected, selectedEdge, deleteNode, deleteEdge]);

  // Nó selecionado que deixou de existir (desfazer, excluir): limpa a seleção.
  useEffect(() => {
    if (selected && selected !== TRIGGER_ID && !nodeById(graph, selected)) setSelected(null);
  }, [graph, selected]);

  const focusNode = (id: string) => {
    setSelected(id);
    setSelectedEdge(null);
    setTab("edit");
    const n = nodeById(graph, id);
    if (n?.position) rf.setCenter(n.position.x + NODE_W / 2, n.position.y + nodeHeight(n) / 2, { zoom: 1, duration: 250 });
  };

  const ui = useMemo<FlowUi>(
    () => ({
      selectedId: selected,
      errorIds,
      used,
      canAddNode,
      hoveredEdgeId: hoveredEdge,
      selectedEdgeId: selectedEdge,
      startId: graph.start,
      highlightId: highlightId ?? null,
      openAddMenu: (nodeId, branch, anchor) => setMenu({ nodeId, branch, anchor }),
      deleteEdge,
    }),
    [selected, errorIds, used, canAddNode, hoveredEdge, selectedEdge, graph.start, highlightId, deleteEdge]
  );

  const selectedNode = selected === TRIGGER_ID ? "trigger" : selected ? (nodeById(graph, selected) ?? null) : null;
  const problems = [...validation.errors.map((i) => ({ ...i, kind: "error" as const })), ...validation.warnings.map((i) => ({ ...i, kind: "warning" as const }))];

  return (
    <FlowUiProvider value={ui}>
      {problems.length > 0 && (
        <Note variant="warning" className="mb-3">
          <p className="mb-1.5 font-medium text-fg">
            {validation.errors.length
              ? `${validation.errors.length} ${validation.errors.length === 1 ? "problema impede" : "problemas impedem"} de salvar`
              : "Avisos"}
            {validation.errors.length > 0 && validation.warnings.length > 0 && ` · ${validation.warnings.length} avisos`}
          </p>
          <ul className="space-y-1">
            {problems.slice(0, 8).map((p, i) => (
              <li key={i}>
                {p.nodeId ? (
                  <button
                    type="button"
                    onClick={() => focusNode(p.nodeId!)}
                    className="flex items-start gap-2 text-left text-fg-2 transition-colors duration-150 ease-out hover:text-fg"
                  >
                    <span
                      aria-hidden
                      className={cx("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", p.kind === "error" ? "bg-negative" : "bg-warning")}
                    />
                    {p.message}
                  </button>
                ) : (
                  <span className="flex items-start gap-2">
                    <span
                      aria-hidden
                      className={cx("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", p.kind === "error" ? "bg-negative" : "bg-warning")}
                    />
                    {p.message}
                  </span>
                )}
              </li>
            ))}
            {problems.length > 8 && <li className="text-fg-3">e mais {problems.length - 8}</li>}
          </ul>
        </Note>
      )}

      <div
        className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]"
        style={{ height: "max(560px, calc(100vh - 56px - 32px))" }}
      >
        {/* ── Canvas ── */}
        <div
          ref={wrapRef}
          className="octus-flow relative min-h-[420px] overflow-hidden rounded-card border border-line bg-bg"
        >
          <ReactFlow
            nodes={rfNodes}
            edges={rfEdges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            onNodesChange={onNodesChange}
            onConnect={onConnect}
            isValidConnection={isValidConnection}
            onNodeClick={(_, n) => {
              setSelected(n.id);
              setSelectedEdge(null);
              setTab((t) => (t === "runs" ? t : "edit"));
            }}
            onEdgeClick={(_, e) => {
              setSelectedEdge(e.id);
              setSelected(null);
            }}
            onPaneClick={() => {
              setSelected(null);
              setSelectedEdge(null);
              setMenu(null);
            }}
            onNodeDragStart={beginGesture}
            onNodeDragStop={endGesture}
            onEdgeMouseEnter={(_, e) => setHoveredEdge(e.id)}
            onEdgeMouseLeave={() => setHoveredEdge(null)}
            nodesConnectable
            nodesDraggable
            elementsSelectable={false}
            deleteKeyCode={null}
            colorMode="dark"
            fitView
            // Abre com o início do fluxo legível (Gatilho, 1º nó e os seguintes); o botão
            // de enquadrar dos controles mostra tudo.
            fitViewOptions={{ nodes: initialFit, padding: 0.2, maxZoom: 1 }}
            minZoom={0.3}
            maxZoom={1.5}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={20} size={1} />
            <Controls showInteractive={false} />

            <Panel position="top-left" className="flex flex-wrap gap-1 rounded-card border border-line bg-card p-1">
              {NODE_TYPES.map((t) => {
                const Icon = NODE_ICON[t];
                return (
                  <Button key={t} variant="ghost" size="sm" icon={Icon} disabled={!canAddNode} onClick={() => addNode(t)}>
                    {NODE_LABEL[t]}
                  </Button>
                );
              })}
            </Panel>

            <Panel position="top-right" className="flex items-center gap-1 rounded-card border border-line bg-card p-1">
              <IconButton icon={Undo2} aria-label="Desfazer" title="Desfazer (Ctrl+Z)" disabled={!canUndo} onClick={undo} />
              <IconButton icon={Redo2} aria-label="Refazer" title="Refazer (Ctrl+Shift+Z)" disabled={!canRedo} onClick={redo} />
              <Button variant="ghost" size="sm" icon={LayoutGrid} disabled={organizing} onClick={organize}>
                {organizing ? "Organizando" : "Organizar"}
              </Button>
            </Panel>
          </ReactFlow>
        </div>

        {/* ── Painel direito ── */}
        <aside className="flex min-h-0 flex-col rounded-card border border-line bg-card">
          <div className="border-b border-line p-3">
            <Segmented<Tab>
              aria-label="Painel do fluxo"
              value={tab}
              onChange={setTab}
              options={[
                { value: "edit", label: "Editar" },
                { value: "preview", label: "Prévia" },
                ...(runsPanel ? [{ value: "runs" as Tab, label: "Execuções" }] : []),
              ]}
            />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {tab === "edit" && (
              <NodeInspector
                node={selectedNode}
                graph={graph}
                isStart={selected === graph.start}
                triggerLabel={triggerLabel}
                patch={(patch, key) => selected && selected !== TRIGGER_ID && patchNode(selected, patch, key)}
                onDelete={() => selected && deleteNode(selected)}
              />
            )}
            {tab === "preview" && (
              <DmPreview
                username={username}
                graph={graph}
                isComment={isComment}
                selectedId={selected && selected !== TRIGGER_ID ? selected : null}
              />
            )}
            {tab === "runs" && runsPanel}
          </div>
        </aside>
      </div>

      {menu && (
        <AddNodeMenu
          anchor={menu.anchor}
          onClose={() => setMenu(null)}
          onPick={(t) => {
            addNode(t, { nodeId: menu.nodeId, branch: menu.branch });
            setMenu(null);
          }}
        />
      )}
    </FlowUiProvider>
  );
}

export default function FlowEditor(props: Parameters<typeof Canvas>[0]) {
  return (
    <ReactFlowProvider>
      <Canvas {...props} />
    </ReactFlowProvider>
  );
}
