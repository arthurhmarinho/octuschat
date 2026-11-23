"use client";

import { Fragment } from "react";
import { BatteryFull, Camera, ChevronLeft, SignalHigh, Wifi } from "lucide-react";
import { cx } from "@/components/ui";
import type { FlowGraph, GraphButton } from "@/lib/flowGraph";
import { firstPath } from "@/lib/flowPath";

/**
 * Preview ao vivo da DM numa moldura de iPhone. As cores aqui reproduzem o
 * Instagram dark (é conteúdo, não chrome do painel), por isso são literais.
 */
const IG = {
  bubble: "bg-[#262626]",
  muted: "text-[#a8a8a8]",
  link: "text-[#e0f1ff]",
};

type Props = {
  username: string;
  graph: FlowGraph;
  /** Gatilho de comentário: a 1ª DM é uma resposta privada. */
  isComment?: boolean;
  /** Mensagem em edição no inspetor (ganha contorno). */
  selectedId?: string | null;
};

const visibleButtons = (buttons?: GraphButton[]) =>
  (buttons ?? []).filter((b) => b.label.trim() || b.url.trim()).slice(0, 3);

function Message({
  text,
  buttons,
  selected,
  dim,
}: {
  text: string;
  buttons: GraphButton[];
  selected: boolean;
  dim: boolean;
}) {
  if (!text.trim() && !buttons.length) return null;
  return (
    <div
      className={cx(
        "max-w-[82%] overflow-hidden rounded-[18px] rounded-bl-[4px] text-[13px] leading-[18px] text-white",
        IG.bubble,
        "transition-[opacity,box-shadow] duration-150 ease-out",
        selected && "shadow-[0_0_0_1.5px_rgba(237,237,237,0.45)]",
        dim && "opacity-60"
      )}
    >
      {text.trim() && <p className="whitespace-pre-wrap break-words px-3 py-2">{text}</p>}
      {buttons.map((b, i) => (
        <div
          key={b.id ?? i}
          className={cx(
            "border-t border-white/10 px-3 py-2.5 text-center font-medium",
            IG.link
          )}
        >
          {b.label.trim() || "Botão"}
        </div>
      ))}
    </div>
  );
}

export default function DmPreview({ username, graph, isComment = false, selectedId = null }: Props) {
  const handle = username || "sua_conta";
  const messages = firstPath(graph).flatMap((n) => (n.type === "message" ? [n] : []));
  const first = messages[0];
  const firstEmpty = !first?.text?.trim() && !visibleButtons(first?.buttons).length;

  return (
    <div className="mx-auto w-[290px] select-none">
      {/* Moldura */}
      <div className="rounded-[44px] border-[10px] border-[#232325] bg-[#0f0f10] shadow-[0_24px_48px_rgba(0,0,0,0.35)]">
        <div className="relative overflow-hidden rounded-[34px] bg-black">
          {/* Dynamic Island */}
          <div className="pointer-events-none absolute left-1/2 top-2 z-20 h-[22px] w-[86px] -translate-x-1/2 rounded-full bg-black" />

          {/* Status bar */}
          <div className="flex items-center justify-between px-6 pb-1 pt-2.5 text-xs font-semibold text-white">
            <span>9:41</span>
            <span className="flex items-center gap-1">
              <SignalHigh size={13} />
              <Wifi size={13} />
              <BatteryFull size={16} />
            </span>
          </div>

          {/* Header da conversa */}
          <div className="flex items-center gap-2.5 border-b border-white/10 px-3 py-2">
            <ChevronLeft size={22} className="shrink-0 text-white" />
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#262626] text-sm font-medium text-[#a8a8a8]">
              {handle.charAt(0).toUpperCase()}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold leading-tight text-white">{handle}</p>
              <p className={cx("text-xs", IG.muted)}>Instagram</p>
            </div>
          </div>

          {/* Mensagens */}
          <div className="min-h-[260px] space-y-1.5 px-3 py-4">
            {isComment && (
              <p className={cx("pb-2 text-center text-xs", IG.muted)}>Respondeu ao seu comentário</p>
            )}

            {firstEmpty ? (
              <div className={cx("max-w-[82%] rounded-[18px] rounded-bl-[4px] bg-[#262626]/60 px-3 py-2 text-[13px]", IG.muted)}>
                Sua mensagem aparece aqui
              </div>
            ) : (
              <Message
                text={first.text ?? ""}
                buttons={visibleButtons(first.buttons)}
                selected={first.id === selectedId}
                dim={false}
              />
            )}

            {messages.slice(1).map((m, i) => {
              const buttons = visibleButtons(m.buttons);
              if (!(m.text ?? "").trim() && !buttons.length) return null;
              return (
                <Fragment key={m.id}>
                  {isComment && i === 0 && (
                    <p className={cx("pb-1 pt-3 text-center text-xs", IG.muted)}>
                      Se a janela de 24h estiver aberta
                    </p>
                  )}
                  <Message
                    text={m.text ?? ""}
                    buttons={buttons}
                    selected={m.id === selectedId}
                    dim={isComment}
                  />
                </Fragment>
              );
            })}
          </div>

          {/* Barra de digitar */}
          <div className="flex items-center gap-2 px-3 pb-2 pt-1">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#262626] text-[#a8a8a8]">
              <Camera size={15} />
            </span>
            <div className={cx("flex-1 rounded-full border border-white/15 px-3 py-1.5 text-xs", IG.muted)}>
              Mensagem
            </div>
          </div>

          {/* Home indicator */}
          <div className="flex justify-center pb-2">
            <div className="h-1 w-24 rounded-full bg-white/30" />
          </div>
        </div>
      </div>
    </div>
  );
}
