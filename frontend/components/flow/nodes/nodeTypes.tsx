"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Clock, GitBranch, Image as ImageIcon, MessageCircleQuestion, MessageSquare } from "lucide-react";
import { KeywordTokens, cx } from "@/components/ui";
import { CONDITION_LABEL, NODE_W, TRIGGER_H, type GraphNode } from "@/lib/flowGraph";
import BaseNode from "./BaseNode";
import { useFlowUi } from "./context";

type Data = { node: GraphNode };
const nodeOf = (p: NodeProps) => (p.data as unknown as Data).node;

/** "2 h", "6 min". */
export function formatHours(h: number | undefined): string {
  if (h == null || Number.isNaN(h)) return "—";
  if (h < 1) return `${Math.round(h * 60)} min`;
  return `${Number.isInteger(h) ? h : h.toFixed(1).replace(".", ",")} h`;
}

function MessageNodeView(p: NodeProps) {
  const n = nodeOf(p);
  if (n.type !== "message") return null;
  const text = (n.text ?? "").trim();
  return <BaseNode node={n} icon={MessageSquare} body={text || "Sem texto"} muted={!text} />;
}

function QuestionNodeView(p: NodeProps) {
  const n = nodeOf(p);
  if (n.type !== "question") return null;
  const text = (n.text ?? "").trim();
  return <BaseNode node={n} icon={MessageCircleQuestion} body={text || "Sem texto"} muted={!text} />;
}

function ConditionNodeView(p: NodeProps) {
  const n = nodeOf(p);
  if (n.type !== "condition") return null;
  const mode = n.mode ?? "text_contains";
  const value = (n.value ?? "").trim();
  let body = CONDITION_LABEL[mode];
  if (mode === "text_contains") body = value ? `Texto contém "${value}"` : "Texto contém…";
  if (mode === "var_contains") body = `{{${n.var || "variável"}}} contém "${value}"`;
  if (mode === "var_exists") body = `{{${n.var || "variável"}}} existe`;
  return <BaseNode node={n} icon={GitBranch} body={body} />;
}

function ImageNodeView(p: NodeProps) {
  const n = nodeOf(p);
  if (n.type !== "image") return null;
  const url = (n.url ?? "").trim();
  return <BaseNode node={n} icon={ImageIcon} body={url || "Sem URL"} muted={!url} />;
}

function DelayNodeView(p: NodeProps) {
  const n = nodeOf(p);
  if (n.type !== "delay") return null;
  return (
    <BaseNode node={n} icon={Clock} body={`A próxima mensagem sai depois de ${formatHours(n.hours)}`} />
  );
}

/** Gatilho: fixo, com saída única. A aresta dele define o início do fluxo. */
function TriggerNodeView({ data }: NodeProps) {
  const ui = useFlowUi();
  const d = data as unknown as { label: string; keywords: string };
  const selected = ui.selectedId === "trigger";
  return (
    <div
      style={{ width: NODE_W, height: TRIGGER_H }}
      className={cx(
        "relative flex flex-col justify-center gap-1.5 rounded-card border px-3",
        "transition-[background-color,border-color] duration-150 ease-out",
        selected ? "border-line-strong bg-raised" : "border-line bg-card hover:border-line-strong"
      )}
    >
      <p className="text-[13px] font-medium text-fg">Gatilho</p>
      <p className="truncate text-[13px] text-fg-2">{d.label}</p>
      {d.keywords ? (
        <KeywordTokens value={d.keywords} className="max-h-5 overflow-hidden" />
      ) : (
        <p className="h-5" />
      )}
      <Handle id="out" type="source" position={Position.Right} className="!h-2 !w-2" />
    </div>
  );
}

export const nodeTypes = {
  trigger: TriggerNodeView,
  message: MessageNodeView,
  question: QuestionNodeView,
  condition: ConditionNodeView,
  image: ImageNodeView,
  delay: DelayNodeView,
};
