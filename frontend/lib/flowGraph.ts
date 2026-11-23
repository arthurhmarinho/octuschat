/**
 * Grafo da automação — espelha `FlowGraph` do backend (schemas/automation.py).
 *
 * `start` é a mensagem 1. `branch` numa aresta é a porta de saída
 * (ausente = saída padrão; "yes"/"no" = ramos de uma condição).
 */

export type GraphButton = { id?: string; type?: "web_url"; label: string; url: string };

export type GraphNode = {
  id: string;
  type?: "message" | "condition";
  text?: string;
  buttons?: GraphButton[];
  mode?: "text_contains" | "is_new_contact";
  value?: string;
  position?: { x: number; y: number };
};

export type GraphEdge = { source: string; target: string; branch?: string };

export type FlowGraph = {
  version: 2;
  start: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

/** Mensagem como o editor a manipula: id do nó + texto + botões de link. */
export type EditorMessage = { id: string; text: string; buttons: GraphButton[] };

export const newNodeId = () => `m-${Math.random().toString(36).slice(2, 9)}`;

const isMessage = (n: GraphNode) => (n.type ?? "message") === "message";

/** Mensagens do caminho padrão a partir do início, até o 1º nó que não é
 * mensagem ou o fim. É o que o canvas e o preview mostram hoje. */
export function linearMessages(graph: FlowGraph | null | undefined): GraphNode[] {
  if (!graph) return [];
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  const out: GraphNode[] = [];
  const seen = new Set<string>();
  let cur: string | undefined = graph.start;
  while (cur && !seen.has(cur)) {
    seen.add(cur);
    const node = byId.get(cur);
    if (!node || !isMessage(node)) break;
    out.push(node);
    cur = graph.edges.find((e) => e.source === cur && !e.branch)?.target;
  }
  return out;
}

/** True se o grafo é só uma cadeia de mensagens (o que o editor sabe editar). */
export function isLinear(graph: FlowGraph | null | undefined): boolean {
  if (!graph) return true;
  return (
    linearMessages(graph).length === graph.nodes.length &&
    graph.edges.every((e) => !e.branch)
  );
}

/** Grafo → estado do editor (mensagens em ordem, cada uma com seus botões). */
export function graphToEditor(graph: FlowGraph | null | undefined): {
  messages: EditorMessage[];
} {
  const msgs = linearMessages(graph);
  if (!msgs.length) return { messages: [{ id: newNodeId(), text: "", buttons: [] }] };
  return {
    messages: msgs.map((n) => ({
      id: n.id,
      text: n.text ?? "",
      buttons: (n.buttons ?? []).map((b) => ({ ...b })),
    })),
  };
}

/** Descarta botões incompletos (sem rótulo ou sem URL) e apara os campos. */
export function cleanMessages(messages: EditorMessage[]): EditorMessage[] {
  return messages.map((m) => ({
    ...m,
    buttons: m.buttons
      .map((b) => ({ ...b, label: b.label.trim(), url: b.url.trim() }))
      .filter((b) => b.label && b.url),
  }));
}

/** Estado do editor → grafo linear. Mensagens seguintes vazias são
 * descartadas; campos que o editor não mostra (posição) são preservados a
 * partir do grafo original. */
export function editorToGraph(
  messages: EditorMessage[],
  base?: FlowGraph | null
): FlowGraph {
  const orig = new Map((base?.nodes ?? []).map((n) => [n.id, n]));
  const kept = messages.filter((m, i) => i === 0 || m.text.trim());
  const nodes: GraphNode[] = kept.map((m) => {
    const node: GraphNode = { ...(orig.get(m.id) ?? {}), id: m.id, type: "message", text: m.text };
    if (m.buttons.length) node.buttons = m.buttons;
    else delete node.buttons;
    return node;
  });
  const edges: GraphEdge[] = nodes
    .slice(1)
    .map((n, i) => ({ source: nodes[i].id, target: n.id }));
  return { version: 2, start: nodes[0].id, nodes, edges };
}
