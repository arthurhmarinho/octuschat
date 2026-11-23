import { NODE_W, TRIGGER_H, nodeHeight, type FlowGraph } from "@/lib/flowGraph";

/**
 * "Organizar": layout em camadas com o elkjs, da esquerda para a direita.
 *
 * O elkjs (~1 MB) é carregado sob demanda: só quem clica em "Organizar" paga o
 * download. As portas de saída ficam na ordem dos handles (`FIXED_ORDER`).
 * Devolve o grafo com as novas posições (o nó do Gatilho é virtual e não entra).
 */
export async function autoLayout(graph: FlowGraph): Promise<FlowGraph> {
  const ELK = (await import("elkjs/lib/elk.bundled.js")).default;
  const elk = new ELK();
  const children = [
    { id: "trigger", width: NODE_W, height: TRIGGER_H },
    ...graph.nodes.map((n) => ({ id: n.id, width: NODE_W, height: nodeHeight(n) })),
  ];
  const edges = [
    { id: "e-trigger", sources: ["trigger"], targets: [graph.start] },
    ...graph.edges.map((e, i) => ({ id: `e${i}`, sources: [e.source], targets: [e.target] })),
  ];
  const result = await elk.layout({
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.layered.spacing.nodeNodeBetweenLayers": "80",
      "elk.spacing.nodeNode": "32",
      "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
    },
    children,
    edges,
  });
  const pos = new Map((result.children ?? []).map((c) => [c.id, { x: c.x ?? 0, y: c.y ?? 0 }]));
  const origin = pos.get("trigger") ?? { x: 0, y: 0 };
  return {
    ...graph,
    nodes: graph.nodes.map((n) => {
      const p = pos.get(n.id);
      return p ? { ...n, position: { x: Math.round(p.x - origin.x + 40), y: Math.round(p.y) } } : n;
    }),
  };
}
