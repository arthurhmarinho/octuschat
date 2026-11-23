import type { Trigger } from "@/lib/automation";
import {
  MAX_BUTTONS,
  MAX_HOURS,
  MAX_NODES,
  MAX_QUICK_REPLIES,
  MIN_HOURS,
  NODE_LABEL,
  QUICK_REPLY_TITLE_MAX,
  VAR_RE,
  byteLength,
  outputsOf,
  textLimit,
  variablesOf,
  type FlowGraph,
  type GraphNode,
} from "@/lib/flowGraph";

export type Issue = { nodeId?: string; message: string };
export type Validation = { errors: Issue[]; warnings: Issue[] };

const isUrl = (s: string) => /^https?:\/\//i.test(s.trim());
const hoursOk = (h: number | undefined) => h != null && h >= MIN_HOURS && h <= MAX_HOURS;

/** Nós alcançáveis a partir do início. */
function reachable(graph: FlowGraph): Set<string> {
  const seen = new Set<string>();
  const stack = [graph.start];
  while (stack.length) {
    const cur = stack.pop()!;
    if (seen.has(cur)) continue;
    seen.add(cur);
    graph.edges.filter((e) => e.source === cur).forEach((e) => stack.push(e.target));
  }
  return seen;
}

function hasCycle(graph: FlowGraph): boolean {
  const indeg = new Map(graph.nodes.map((n) => [n.id, 0]));
  graph.edges.forEach((e) => indeg.set(e.target, (indeg.get(e.target) ?? 0) + 1));
  const queue = [...indeg].filter(([, d]) => d === 0).map(([id]) => id);
  let seen = 0;
  while (queue.length) {
    const cur = queue.pop()!;
    seen++;
    for (const e of graph.edges.filter((x) => x.source === cur)) {
      const d = (indeg.get(e.target) ?? 0) - 1;
      indeg.set(e.target, d);
      if (d === 0) queue.push(e.target);
    }
  }
  return seen !== graph.nodes.length;
}

function validateNode(node: GraphNode, graph: FlowGraph, errors: Issue[], warnings: Issue[]) {
  const err = (message: string) => errors.push({ nodeId: node.id, message });
  const isStart = node.id === graph.start;
  const label = NODE_LABEL[node.type];

  switch (node.type) {
    case "message": {
      const text = node.text ?? "";
      const buttons = node.buttons ?? [];
      const replies = node.quick_replies ?? [];
      if (!text.trim() && !buttons.length && !replies.length) err(`${label}: escreva o texto`);
      else if (isStart && !text.trim()) err(`${label}: a primeira mensagem precisa de texto`);
      if (buttons.length && replies.length) err(`${label}: botões e respostas rápidas não podem ficar juntos`);
      if (replies.length && !text.trim()) err(`${label}: respostas rápidas precisam de texto`);
      const limit = textLimit(node);
      if (byteLength(text) > limit) err(`${label}: o texto passa de ${limit} bytes`);
      if (buttons.length > MAX_BUTTONS) err(`${label}: no máximo ${MAX_BUTTONS} botões`);
      buttons.forEach((b, i) => {
        if ((b.label.trim() || b.url.trim()) && !b.label.trim()) err(`${label}: o botão ${i + 1} precisa de um rótulo`);
        if (b.url.trim() && !isUrl(b.url)) err(`${label}: a URL do botão ${i + 1} precisa começar com http:// ou https://`);
      });
      if (replies.length > MAX_QUICK_REPLIES) err(`${label}: no máximo ${MAX_QUICK_REPLIES} respostas rápidas`);
      replies.forEach((q, i) => {
        if (!q.title.trim()) err(`${label}: a resposta rápida ${i + 1} precisa de um título`);
        else if (q.title.length > QUICK_REPLY_TITLE_MAX)
          err(`${label}: o título da resposta rápida ${i + 1} passa de ${QUICK_REPLY_TITLE_MAX} caracteres`);
      });
      if (node.timeout_hours != null && replies.length && !hoursOk(node.timeout_hours))
        err(`${label}: o tempo de espera vai de ${MIN_HOURS} a ${MAX_HOURS} horas`);
      break;
    }
    case "question": {
      const text = node.text ?? "";
      if (!text.trim()) err(`${label}: escreva a pergunta`);
      if (byteLength(text) > 1000) err(`${label}: o texto passa de 1000 bytes`);
      if (!VAR_RE.test(node.save_as ?? ""))
        err(`${label}: o nome da variável usa letras minúsculas, números e _ (começa com letra)`);
      if (node.timeout_hours != null && !hoursOk(node.timeout_hours))
        err(`${label}: o tempo de espera vai de ${MIN_HOURS} a ${MAX_HOURS} horas`);
      break;
    }
    case "condition": {
      const mode = node.mode;
      if (!mode) err(`${label}: escolha o modo`);
      if ((mode === "text_contains" || mode === "var_contains") && !(node.value ?? "").trim())
        err(`${label}: informe o valor`);
      if ((mode === "var_contains" || mode === "var_exists") && !VAR_RE.test(node.var ?? ""))
        err(`${label}: escolha a variável`);
      else if (
        (mode === "var_contains" || mode === "var_exists") &&
        !variablesOf(graph).includes(node.var ?? "")
      )
        warnings.push({ nodeId: node.id, message: `${label}: nenhuma Pergunta salva a variável {{${node.var}}}` });
      break;
    }
    case "image":
      if (!isUrl(node.url ?? "")) err(`${label}: a URL precisa começar com http:// ou https://`);
      break;
    case "delay":
      if (!hoursOk(node.hours)) err(`${label}: a espera vai de ${MIN_HOURS} a ${MAX_HOURS} horas`);
      break;
  }
}

/** Espelha as regras do backend (schemas/automation.py). Erros bloqueiam o salvar; avisos não. */
export function validateGraph(graph: FlowGraph, trigger: Trigger): Validation {
  const errors: Issue[] = [];
  const warnings: Issue[] = [];
  const isComment = trigger === "comment_any" || trigger === "comment_keyword";

  if (graph.nodes.length > MAX_NODES) errors.push({ message: `O fluxo pode ter no máximo ${MAX_NODES} nós` });

  graph.nodes.forEach((n) => validateNode(n, graph, errors, warnings));

  const start = graph.nodes.find((n) => n.id === graph.start);
  if (!start) {
    errors.push({ message: "O Gatilho precisa estar ligado a um nó" });
  } else {
    if (start.type !== "message" && start.type !== "question" && start.type !== "image")
      errors.push({ nodeId: start.id, message: "O primeiro nó precisa ser uma mensagem, pergunta ou imagem" });
    else if (isComment && start.type !== "message")
      errors.push({ nodeId: start.id, message: "No gatilho de comentário o primeiro nó precisa ser uma mensagem" });
    if (isComment && start.type === "message" && start.quick_replies?.length)
      warnings.push({
        nodeId: start.id,
        message: "Respostas rápidas na resposta privada ao comentário podem não aparecer. Teste com uma conta real",
      });
    if (graph.edges.some((e) => e.target === start.id))
      errors.push({ nodeId: start.id, message: "O primeiro nó não pode receber ligações de outros nós" });
  }

  if (hasCycle(graph)) errors.push({ message: "O fluxo não pode ter ciclos" });

  const ports = new Set<string>();
  for (const e of graph.edges) {
    const source = graph.nodes.find((n) => n.id === e.source);
    if (!source || !outputsOf(source).some((o) => (o.branch ?? "") === (e.branch ?? "")))
      errors.push({ nodeId: e.source, message: "Há uma ligação saindo de uma opção que não existe mais" });
    const key = `${e.source}|${e.branch ?? ""}`;
    if (ports.has(key)) errors.push({ nodeId: e.source, message: "Uma saída está ligada a mais de um nó" });
    ports.add(key);
  }

  if (start) {
    const seen = reachable(graph);
    graph.nodes
      .filter((n) => !seen.has(n.id))
      .forEach((n) =>
        warnings.push({ nodeId: n.id, message: `${NODE_LABEL[n.type]} sem ligação: nunca será executado` })
      );
  }
  return { errors, warnings };
}
