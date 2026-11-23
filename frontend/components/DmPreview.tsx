"use client";

import { Fragment, useState } from "react";
import { BatteryFull, Camera, ChevronLeft, SignalHigh, Wifi } from "lucide-react";
import { cx } from "@/components/ui";
import type { Bubble, Segment } from "@/lib/flowPath";

/**
 * Prévia ao vivo da DM numa moldura de iPhone. As cores aqui reproduzem o
 * Instagram dark (é conteúdo, não chrome do painel), por isso são literais.
 */
const IG = {
  bubble: "bg-[#262626]",
  mine: "bg-[#3797f0]",
  muted: "text-[#a8a8a8]",
  link: "text-[#e0f1ff]",
};

type Props = {
  username: string;
  bubbles: Bubble[];
  /** Gatilho de comentário: a 1ª DM é uma resposta privada. */
  isComment?: boolean;
  /** Nó selecionado no canvas (suas bolhas ganham contorno). */
  selectedId?: string | null;
};

function Text({ segments }: { segments: Segment[] }) {
  return (
    <>
      {segments.map((s, i) =>
        s.variable ? (
          <span key={i} className="text-[#8e8e8e]">
            {s.text}
          </span>
        ) : (
          <Fragment key={i}>{s.text}</Fragment>
        )
      )}
    </>
  );
}

const ring = (on: boolean) => on && "shadow-[0_0_0_1.5px_rgba(237,237,237,0.45)]";

function Image({ url, selected }: { url: string; selected: boolean }) {
  const [broken, setBroken] = useState(false);
  return (
    <div
      className={cx(
        "max-w-[70%] overflow-hidden rounded-[18px] rounded-bl-[4px]",
        IG.bubble,
        "transition-shadow duration-150 ease-out",
        ring(selected)
      )}
    >
      {broken ? (
        <div className={cx("flex h-28 w-40 items-center justify-center px-3 text-center text-xs", IG.muted)}>
          Não foi possível carregar a imagem
        </div>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt="Imagem do fluxo" className="max-h-52 w-full object-cover" onError={() => setBroken(true)} />
      )}
    </div>
  );
}

export default function DmPreview({ username, bubbles, isComment = false, selectedId = null }: Props) {
  const handle = username || "sua_conta";
  const empty = bubbles.length === 0;
  const lastIdx = bubbles.reduce((acc, b, i) => (b.kind === "text" ? i : acc), -1);
  const firstText = bubbles.findIndex((b) => b.kind === "text");

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
          <div className="min-h-[300px] space-y-1.5 px-3 py-4">
            {isComment && (
              <p className={cx("pb-2 text-center text-xs", IG.muted)}>Respondeu ao seu comentário</p>
            )}

            {empty && (
              <div className={cx("max-w-[82%] rounded-[18px] rounded-bl-[4px] bg-[#262626]/60 px-3 py-2 text-[13px]", IG.muted)}>
                Sua mensagem aparece aqui
              </div>
            )}

            {bubbles.map((b, i) => {
              const selected = b.nodeId === selectedId;
              if (b.kind === "divider") {
                return (
                  <p key={i} className={cx("py-1.5 text-center text-xs", IG.muted)}>
                    {b.text}
                  </p>
                );
              }
              if (b.kind === "user") {
                return (
                  <div key={i} className="flex justify-end">
                    <div
                      className={cx(
                        "max-w-[75%] rounded-[18px] rounded-br-[4px] px-3 py-2 text-[13px] leading-[18px] text-white",
                        IG.mine,
                        "transition-shadow duration-150 ease-out",
                        ring(selected)
                      )}
                    >
                      {b.text}
                    </div>
                  </div>
                );
              }
              if (b.kind === "image") return <Image key={i} url={b.url} selected={selected} />;
              return (
                <Fragment key={i}>
                  {isComment && i === firstText + 1 && (
                    <p className={cx("pb-1 pt-3 text-center text-xs", IG.muted)}>
                      Se a janela de 24h estiver aberta
                    </p>
                  )}
                  <div
                    className={cx(
                      "max-w-[82%] overflow-hidden rounded-[18px] rounded-bl-[4px] text-[13px] leading-[18px] text-white",
                      IG.bubble,
                      "transition-[opacity,box-shadow] duration-150 ease-out",
                      ring(selected),
                      isComment && firstText >= 0 && i > firstText && "opacity-60"
                    )}
                  >
                    {b.segments.length > 0 && (
                      <p className="whitespace-pre-wrap break-words px-3 py-2">
                        <Text segments={b.segments} />
                      </p>
                    )}
                    {b.buttons.map((btn, j) => (
                      <div
                        key={btn.id ?? j}
                        className={cx("border-t border-white/10 px-3 py-2.5 text-center font-medium", IG.link)}
                      >
                        {btn.label.trim() || "Botão"}
                      </div>
                    ))}
                  </div>
                  {/* Respostas rápidas: chips abaixo da última mensagem, como no Instagram */}
                  {b.replies.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-0.5">
                      {b.replies.map((r, j) => (
                        <span
                          key={j}
                          className={cx(
                            "rounded-full border border-white/25 px-3 py-1.5 text-[13px] text-white",
                            i !== lastIdx && "opacity-50"
                          )}
                        >
                          {r}
                        </span>
                      ))}
                    </div>
                  )}
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
