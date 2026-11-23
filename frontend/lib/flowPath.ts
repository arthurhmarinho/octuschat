import { outputsOf, type FlowGraph, type GraphNode } from "@/lib/flowGraph";

/**
 * Caminho do início até onde a prévia mostra: segue, em cada nó, a primeira
 * saída que tem ligação. Para no fim, em ciclo (não deveria haver) ou quando
 * `stopAt` é alcançado (inclusive).
 */
export function firstPath(graph: FlowGraph, stopAt?: string | null): GraphNode[] {
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  const out: GraphNode[] = [];
  const seen = new Set<string>();
  let cur: string | undefined = graph.start;
  while (cur && !seen.has(cur)) {
    seen.add(cur);
    const node = byId.get(cur);
    if (!node) break;
    out.push(node);
    if (stopAt && node.id === stopAt) break;
    const edge = outputsOf(node)
      .map((o) => graph.edges.find((e) => e.source === node.id && (e.branch ?? "") === (o.branch ?? "")))
      .find(Boolean);
    cur = edge?.target;
  }
  return out;
}
