/**
 * Grafo da automação — espelha `FlowGraph` do backend (schemas/automation.py).
 *
 * Versão 3 (a que o editor grava):
 *
 *   { version: 3, start: "n1",
 *     nodes: [message | question | condition | image | delay],
 *     edges: [{ source, target, branch? }] }
 *
 * `branch` é a SAÍDA do nó de origem (ver `outputsOf`). Saída sem aresta é o
 * fim daquele caminho. Grafos v2 (só `message`/`condition`) continuam válidos.
 *
 * O editor trabalha direto com este grafo: o nó do Gatilho é virtual (id
 * `TRIGGER_ID`) e a aresta dele define `start`.
 */

export const TRIGGER_ID = "trigger";

// Limites (iguais aos do backend; o backend é quem manda).
export const MAX_NODES = 50;
export const MAX_BUTTONS = 3;
export const MAX_QUICK_REPLIES = 13;
export const QUICK_REPLY_TITLE_MAX = 20;
export const MAX_TEXT_BYTES = 1000;
export const MAX_TEXT_BYTES_WITH_BUTTONS = 640;
export const MIN_HOURS = 0.1;
export const MAX_HOURS = 23;
export const VAR_RE = /^[a-z][a-z0-9_]{0,29}$/;

export type GraphButton = { id?: string; type?: "web_url"; label: string; url: string };
export type QuickReply = { id: string; title: string };
export type ConditionMode = "text_contains" | "is_new_contact" | "var_contains" | "var_exists";
export type NodeType = "message" | "question" | "condition" | "image" | "delay";

type Base = { id: string; position?: { x: number; y: number } };
export type MessageNode = Base & {
  type: "message";
  text?: string;
  buttons?: GraphButton[];
  quick_replies?: QuickReply[];
  timeout_hours?: number;
};
export type QuestionNode = Base & {
  type: "question";
  text?: string;
  save_as?: string;
  timeout_hours?: number;
};
export type ConditionNode = Base & {
  type: "condition";
  mode?: ConditionMode;
  value?: string;
  var?: string;
};
export type ImageNode = Base & { type: "image"; url?: string };
export type DelayNode = Base & { type: "delay"; hours?: number };
export type GraphNode = MessageNode | QuestionNode | ConditionNode | ImageNode | DelayNode;

export type GraphEdge = { source: string; target: string; branch?: string };

export type FlowGraph = {
  version: 2 | 3;
  start: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

// ── Textos ──────────────────────────────────────────────────

/** Tamanho como a Meta conta: bytes UTF-8 (o emoji pesa 4). */
export const byteLength = (s: string): number => new TextEncoder().encode(s).length;

export const textLimit = (node: MessageNode): number =>
  node.buttons?.length ? MAX_TEXT_BYTES_WITH_BUTTONS : MAX_TEXT_BYTES;

export const newNodeId = () => `n-${Math.random().toString(36).slice(2, 9)}`;
export const newItemId = (prefix: string) => `${prefix}${Math.random().toString(36).slice(2, 6)}`;

export const NODE_LABEL: Record<NodeType, string> = {
  message: "Mensagem",
  question: "Pergunta",
  condition: "Condição",
  image: "Imagem",
  delay: "Esperar",
};

export const CONDITION_LABEL: Record<ConditionMode, string> = {
  text_contains: "Texto contém",
  is_new_contact: "Contato novo",
  var_contains: "Variável contém",
  var_exists: "Variável existe",
};

// ── Saídas ──────────────────────────────────────────────────

/** Id do handle da saída padrão (sem `branch`). */
export const DEFAULT_HANDLE = "out";

export type Output = {
  /** Id do handle no React Flow. */
  handle: string;
  /** `branch` gravado na aresta (null = saída padrão). */
  branch: string | null;
  label: string;
};

/** Saídas de um nó, na ordem em que aparecem (e em que o layout as porta). */
export function outputsOf(node: GraphNode): Output[] {
  switch (node.type) {
    case "message": {
      const replies = node.quick_replies ?? [];
      if (!replies.length) return [{ handle: DEFAULT_HANDLE, branch: null, label: "Próxima" }];
      return [
        ...replies.map((q, i) => ({
          handle: `qr:${q.id}`,
          branch: `qr:${q.id}`,
          label: q.title.trim() || `Opção ${i + 1}`,
        })),
        { handle: "other", branch: "other", label: "Outro texto" },
        { handle: "timeout", branch: "timeout", label: "Sem resposta" },
      ];
    }
    case "question":
      return [
        { handle: "answered", branch: "answered", label: "Respondeu" },
        { handle: "timeout", branch: "timeout", label: "Sem resposta" },
      ];
    case "condition":
      return [
        { handle: "yes", branch: "yes", label: "Sim" },
        { handle: "no", branch: "no", label: "Não" },
      ];
    default:
      return [{ handle: DEFAULT_HANDLE, branch: null, label: "Próxima" }];
  }
}

export const handleOfBranch = (branch: string | null | undefined): string => branch || DEFAULT_HANDLE;
export const branchOfHandle = (handle: string | null | undefined): string | null =>
  !handle || handle === DEFAULT_HANDLE ? null : handle;

export const nodeById = (graph: FlowGraph, id: string): GraphNode | undefined =>
  graph.nodes.find((n) => n.id === id);

/** Saídas ocupadas (já têm aresta): `source|branch`. */
export function usedOutputs(graph: FlowGraph): Set<string> {
  return new Set(graph.edges.map((e) => `${e.source}|${e.branch ?? ""}`));
}

/** Remove arestas que apontam para saídas ou nós que deixaram de existir. */
export function pruneEdges(graph: FlowGraph): FlowGraph {
  const ids = new Set(graph.nodes.map((n) => n.id));
  const valid = new Map(graph.nodes.map((n) => [n.id, new Set(outputsOf(n).map((o) => o.branch ?? ""))]));
  const edges = graph.edges.filter(
    (e) => ids.has(e.source) && ids.has(e.target) && valid.get(e.source)?.has(e.branch ?? "")
  );
  return edges.length === graph.edges.length ? graph : { ...graph, edges };
}

/** Variáveis criadas pelas Perguntas do grafo. */
export function variablesOf(graph: FlowGraph): string[] {
  const out: string[] = [];
  for (const n of graph.nodes) {
    if (n.type === "question" && n.save_as && VAR_RE.test(n.save_as) && !out.includes(n.save_as)) {
      out.push(n.save_as);
    }
  }
  return out;
}

/** True se ligar `source` → `target` fecharia um ciclo (target já alcança source). */
export function wouldCycle(graph: FlowGraph, source: string, target: string): boolean {
  if (source === target) return true;
  const next = new Map<string, string[]>();
  for (const e of graph.edges) next.set(e.source, [...(next.get(e.source) ?? []), e.target]);
  const seen = new Set<string>();
  const stack = [target];
  while (stack.length) {
    const cur = stack.pop()!;
    if (cur === source) return true;
    if (seen.has(cur)) continue;
    seen.add(cur);
    stack.push(...(next.get(cur) ?? []));
  }
  return false;
}

// ── Dimensões (explícitas: o canvas não depende de medição do DOM) ──

export const NODE_W = 280;
const PAD = 12;
const HEADER_H = 20;
const BODY_H = 36; // 2 linhas
const META_H = 16;
const OUT_H = 28;
const GAP_Y = 8;

/** Texto curto de meta (contagens) mostrado abaixo do corpo; vazio = sem linha. */
export function metaOf(node: GraphNode): string {
  switch (node.type) {
    case "message": {
      const b = node.buttons?.length ?? 0;
      const q = node.quick_replies?.length ?? 0;
      if (b) return `${b} ${b === 1 ? "botão" : "botões"}`;
      if (q) return `${q} ${q === 1 ? "resposta rápida" : "respostas rápidas"}`;
      return "";
    }
    case "question":
      return node.save_as ? `salva em {{${node.save_as}}}` : "";
    case "condition":
      return "";
    case "image":
      return "";
    case "delay":
      return "";
  }
}

export function nodeHeight(node: GraphNode): number {
  const meta = metaOf(node) ? META_H + GAP_Y : 0;
  return PAD + HEADER_H + GAP_Y + BODY_H + meta + GAP_Y + outputsOf(node).length * OUT_H + PAD;
}

/** Y (relativo ao nó) do centro da saída `index`. */
export function outputY(node: GraphNode, index: number): number {
  const meta = metaOf(node) ? META_H + GAP_Y : 0;
  const top = PAD + HEADER_H + GAP_Y + BODY_H + meta + GAP_Y;
  return top + index * OUT_H + OUT_H / 2;
}

export const TRIGGER_H = 84;
export const INPUT_Y = PAD + HEADER_H / 2;

// ── Normalização e layout inicial ───────────────────────────

/** Layout em camadas, simples e síncrono (esquerda → direita), para grafos sem posições. */
export function layoutSync(graph: FlowGraph): FlowGraph {
  const depth = new Map<string, number>([[graph.start, 0]]);
  const queue = [graph.start];
  while (queue.length) {
    const cur = queue.shift()!;
    for (const e of graph.edges.filter((x) => x.source === cur)) {
      const d = (depth.get(cur) ?? 0) + 1;
      if (!depth.has(e.target) || (depth.get(e.target) ?? 0) < d) {
        depth.set(e.target, d);
        queue.push(e.target);
      }
    }
  }
  // Nós soltos vão depois da última camada.
  const maxDepth = Math.max(0, ...depth.values());
  graph.nodes.forEach((n) => {
    if (!depth.has(n.id)) depth.set(n.id, maxDepth + 1);
  });
  const cols = new Map<number, GraphNode[]>();
  graph.nodes.forEach((n) => cols.set(depth.get(n.id)!, [...(cols.get(depth.get(n.id)!) ?? []), n]));
  const positioned = new Map<string, { x: number; y: number }>();
  for (const [d, nodes] of cols) {
    let y = 0;
    for (const n of nodes) {
      positioned.set(n.id, { x: 340 * (d + 1), y });
      y += nodeHeight(n) + 32;
    }
  }
  return { ...graph, nodes: graph.nodes.map((n) => ({ ...n, position: positioned.get(n.id) })) };
}

/** Garante o formato v3, ao menos um nó e posições (aplica o layout uma vez se faltarem). */
export function normalizeGraph(graph: FlowGraph | null | undefined): FlowGraph {
  if (!graph || !graph.nodes?.length) {
    const id = newNodeId();
    return {
      version: 3,
      start: id,
      nodes: [{ id, type: "message", text: "", position: { x: 340, y: 0 } }],
      edges: [],
    };
  }
  const nodes = graph.nodes.map((n) => ({ ...n, type: n.type ?? "message" })) as GraphNode[];
  const g: FlowGraph = {
    version: 3,
    start: graph.start && nodes.some((n) => n.id === graph.start) ? graph.start : nodes[0].id,
    nodes,
    edges: (graph.edges ?? []).map((e) => ({ ...e })),
  };
  return nodes.some((n) => !n.position) ? layoutSync(g) : g;
}

// ── Saída para a API ────────────────────────────────────────

/** Grafo limpo para enviar: apara textos, descarta botões e respostas incompletos. */
export function toApiGraph(graph: FlowGraph): FlowGraph {
  const nodes = graph.nodes.map((n): GraphNode => {
    const base = { id: n.id, position: n.position };
    switch (n.type) {
      case "message": {
        const buttons = (n.buttons ?? [])
          .map((b) => ({ ...b, label: b.label.trim(), url: b.url.trim() }))
          .filter((b) => b.label && b.url);
        const replies = (n.quick_replies ?? [])
          .map((q) => ({ ...q, title: q.title.trim() }))
          .filter((q) => q.title);
        const out: MessageNode = { ...base, type: "message", text: n.text ?? "" };
        if (buttons.length) out.buttons = buttons;
        if (replies.length) {
          out.quick_replies = replies;
          if (n.timeout_hours != null) out.timeout_hours = n.timeout_hours;
        }
        return out;
      }
      case "question": {
        const out: QuestionNode = { ...base, type: "question", text: n.text ?? "", save_as: n.save_as ?? "" };
        if (n.timeout_hours != null) out.timeout_hours = n.timeout_hours;
        return out;
      }
      case "condition": {
        const mode = n.mode ?? "text_contains";
        const out: ConditionNode = { ...base, type: "condition", mode };
        if (mode === "text_contains" || mode === "var_contains") out.value = (n.value ?? "").trim();
        if (mode === "var_contains" || mode === "var_exists") out.var = n.var ?? "";
        return out;
      }
      case "image":
        return { ...base, type: "image", url: (n.url ?? "").trim() };
      case "delay":
        return { ...base, type: "delay", hours: n.hours ?? 1 };
    }
  });
  const g = pruneEdges({ ...graph, nodes });
  return { version: 3, start: g.start, nodes: g.nodes, edges: g.edges };
}

/** Novo nó vazio de um tipo (com posição). */
export function makeNode(type: NodeType, position: { x: number; y: number }): GraphNode {
  const id = newNodeId();
  switch (type) {
    case "message":
      return { id, type, text: "", position };
    case "question":
      return { id, type, text: "", save_as: "resposta", position };
    case "condition":
      return { id, type, mode: "text_contains", value: "", position };
    case "image":
      return { id, type, url: "", position };
    case "delay":
      return { id, type, hours: 1, position };
  }
}
