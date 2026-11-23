import {
  outputsOf,
  type FlowGraph,
  type GraphButton,
  type GraphNode,
  type Output,
} from "@/lib/flowGraph";

/**
 * Caminho do início até onde a prévia mostra: segue, em cada nó, a saída que o
 * usuário escolheu (`choices[nodeId]` = `branch` ou "" para a saída padrão) ou,
 * sem escolha, a primeira saída que tem ligação. Para no fim, em ciclo (não
 * deveria haver) ou quando `stopAt` é alcançado (inclusive).
 */
export function pathFrom(
  graph: FlowGraph,
  stopAt?: string | null,
  choices: Record<string, string> = {}
): { node: GraphNode; taken: Output | null }[] {
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  const out: { node: GraphNode; taken: Output | null }[] = [];
  const seen = new Set<string>();
  let cur: string | undefined = graph.start;
  while (cur && !seen.has(cur)) {
    seen.add(cur);
    const node = byId.get(cur);
    if (!node) break;
    const outputs = outputsOf(node);
    const edgeOf = (o: Output) =>
      graph.edges.find((e) => e.source === node.id && (e.branch ?? "") === (o.branch ?? ""));
    const chosen = choices[node.id] !== undefined ? outputs.find((o) => (o.branch ?? "") === choices[node.id]) : undefined;
    const taken = (chosen && edgeOf(chosen) ? chosen : undefined) ?? outputs.find((o) => edgeOf(o)) ?? null;
    out.push({ node, taken });
    if (stopAt && node.id === stopAt) break;
    cur = taken ? edgeOf(taken)?.target : undefined;
  }
  return out;
}

/** Texto com variáveis: `username` já trocado pelo @ real; as demais ficam como chips cinza. */
export type Segment = { text: string; variable?: boolean };

export function renderSegments(text: string, username: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  for (const m of text.matchAll(/\{\{\s*([a-z][a-z0-9_]*)\s*\}\}/g)) {
    if (m.index! > last) out.push({ text: text.slice(last, m.index) });
    if (m[1] === "username") out.push({ text: username || "sua_conta" });
    else out.push({ text: `{{${m[1]}}}`, variable: true });
    last = m.index! + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
}

export type Bubble =
  | { kind: "text"; nodeId: string; segments: Segment[]; buttons: GraphButton[]; replies: string[] }
  | { kind: "image"; nodeId: string; url: string }
  /** Resposta simulada do contato (bolha à direita). */
  | { kind: "user"; nodeId: string; text: string }
  /** Separador fino ("2 h depois", "Sem resposta"). */
  | { kind: "divider"; nodeId: string; text: string };

const hoursText = (h: number | undefined) => {
  if (h == null) return "";
  if (h < 1) return `${Math.round(h * 60)} min`;
  return `${Number.isInteger(h) ? h : h.toFixed(1).replace(".", ",")} h`;
};

/** Bolhas da prévia, na ordem em que o contato as vê. */
export function buildBubbles(
  graph: FlowGraph,
  username: string,
  stopAt?: string | null,
  choices: Record<string, string> = {}
): Bubble[] {
  const bubbles: Bubble[] = [];
  for (const { node, taken } of pathFrom(graph, stopAt, choices)) {
    switch (node.type) {
      case "message": {
        const buttons = (node.buttons ?? []).filter((b) => b.label.trim() || b.url.trim()).slice(0, 3);
        const replies = (node.quick_replies ?? []).map((q) => q.title.trim()).filter(Boolean);
        if ((node.text ?? "").trim() || buttons.length || replies.length) {
          bubbles.push({
            kind: "text",
            nodeId: node.id,
            segments: renderSegments((node.text ?? "").trim(), username),
            buttons,
            replies,
          });
        }
        if (replies.length && taken) {
          if (taken.branch?.startsWith("qr:")) {
            bubbles.push({ kind: "user", nodeId: node.id, text: taken.label });
          } else if (taken.branch === "other") {
            bubbles.push({ kind: "user", nodeId: node.id, text: "Resposta" });
          } else if (taken.branch === "timeout") {
            bubbles.push({ kind: "divider", nodeId: node.id, text: "Sem resposta" });
          }
        }
        break;
      }
      case "question":
        bubbles.push({
          kind: "text",
          nodeId: node.id,
          segments: renderSegments((node.text ?? "").trim(), username),
          buttons: [],
          replies: [],
        });
        if (taken?.branch === "timeout") bubbles.push({ kind: "divider", nodeId: node.id, text: "Sem resposta" });
        else if (taken) bubbles.push({ kind: "user", nodeId: node.id, text: "Resposta" });
        break;
      case "image":
        if ((node.url ?? "").trim()) bubbles.push({ kind: "image", nodeId: node.id, url: node.url!.trim() });
        break;
      case "delay":
        bubbles.push({ kind: "divider", nodeId: node.id, text: `${hoursText(node.hours)} depois` });
        break;
      case "condition":
        break;
    }
  }
  return bubbles;
}
