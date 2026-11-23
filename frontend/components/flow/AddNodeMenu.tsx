"use client";

import { Clock, GitBranch, Image as ImageIcon, MessageCircleQuestion, MessageSquare, type LucideIcon } from "lucide-react";
import { useEffect, useRef } from "react";
import { NODE_LABEL, type NodeType } from "@/lib/flowGraph";

export const NODE_ICON: Record<NodeType, LucideIcon> = {
  message: MessageSquare,
  question: MessageCircleQuestion,
  condition: GitBranch,
  image: ImageIcon,
  delay: Clock,
};

export const NODE_TYPES: NodeType[] = ["message", "question", "condition", "image", "delay"];

/**
 * Menu dos 5 tipos de nó, aberto pelo "+" de uma saída. Fica fora do nó
 * (posição fixa na tela) para não ser coberto por outros nós.
 */
export default function AddNodeMenu({
  anchor,
  onPick,
  onClose,
}: {
  anchor: DOMRect;
  onPick: (type: NodeType) => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    ref.current?.querySelector("button")?.focus();
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  // Abre à direita da saída; se faltar espaço, para a esquerda / sobe.
  const W = 176;
  const H = 5 * 32 + 8;
  const left = anchor.right + 8 + W > window.innerWidth ? anchor.left - W - 8 : anchor.right + 8;
  const top = Math.min(Math.max(8, anchor.top - 8), window.innerHeight - H - 8);

  return (
    <div
      ref={ref}
      role="menu"
      aria-label="Adicionar nó"
      style={{ left, top, width: W }}
      className="fixed z-[65] rounded-card border border-line-strong bg-raised p-1 shadow-[0_8px_24px_rgba(0,0,0,0.4)]"
    >
      {NODE_TYPES.map((t) => {
        const Icon = NODE_ICON[t];
        return (
          <button
            key={t}
            type="button"
            role="menuitem"
            onClick={() => onPick(t)}
            className="flex h-8 w-full items-center gap-2 rounded-control px-2 text-[13px] text-fg-2 transition-colors duration-150 ease-out hover:bg-card hover:text-fg"
          >
            <Icon size={16} strokeWidth={1.5} className="text-fg-3" />
            {NODE_LABEL[t]}
          </button>
        );
      })}
    </div>
  );
}
