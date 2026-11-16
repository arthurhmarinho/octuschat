"use client";

import { Instagram, ChevronLeft, Wifi, BatteryFull, SignalHigh, Camera } from "lucide-react";

import { linearMessages, type FlowGraph, type GraphButton } from "@/lib/flowGraph";

type Props = {
  username: string;
  graph: FlowGraph;
};

const bubble =
  "max-w-[82%] whitespace-pre-wrap break-words rounded-2xl rounded-tl-md bg-neutral-800 px-3 py-2 text-sm text-white";

/** Botões (button template) empilhados. */
function Buttons({ buttons }: { buttons: GraphButton[] }) {
  return (
    <div className="max-w-[82%] overflow-hidden rounded-2xl border border-neutral-700 bg-neutral-900">
      {buttons.slice(0, 3).map((b, i) => (
        <div
          key={b.id ?? i}
          className={`px-3 py-2.5 text-center text-sm font-medium text-blue-400 ${
            i > 0 ? "border-t border-neutral-700" : ""
          }`}
        >
          {b.label.trim() || "Botão"}
        </div>
      ))}
    </div>
  );
}

/**
 * Preview ao vivo da DM, renderizado dentro de uma moldura de iPhone
 * (dynamic island + status bar + header do Instagram + barra de digitar).
 * Mostra as mensagens do caminho padrão do grafo, a partir do início.
 */
export default function DmPreview({ username, graph }: Props) {
  const handle = username || "sua_conta";
  const [first, ...rest] = linearMessages(graph);
  const text = first?.text ?? "";
  const validButtons = (first?.buttons ?? []).filter((b) => b.label.trim() || b.url.trim());

  return (
    <div className="mx-auto w-[290px] select-none">
      {/* Moldura do iPhone */}
      <div className="rounded-[2.7rem] border-[10px] border-neutral-800 bg-neutral-800 shadow-2xl">
        <div className="relative overflow-hidden rounded-[2.1rem] bg-black">
          {/* Dynamic Island */}
          <div className="pointer-events-none absolute left-1/2 top-2 z-20 h-[22px] w-[86px] -translate-x-1/2 rounded-full bg-black" />

          {/* Status bar */}
          <div className="flex items-center justify-between px-6 pt-2.5 pb-1 text-[11px] font-semibold text-white">
            <span>9:41</span>
            <span className="flex items-center gap-1">
              <SignalHigh size={13} />
              <Wifi size={13} />
              <BatteryFull size={16} />
            </span>
          </div>

          {/* Header da conversa (Instagram) */}
          <div className="flex items-center gap-2.5 border-b border-neutral-800/80 px-3 py-2">
            <ChevronLeft size={22} className="shrink-0 text-white" />
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-tr from-yellow-400 via-pink-500 to-purple-600">
              <Instagram size={16} className="text-white" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold leading-tight">{handle}</p>
              <p className="text-[10px] text-neutral-500">Instagram</p>
            </div>
          </div>

          {/* Mensagens */}
          <div className="min-h-[210px] space-y-2 px-3 py-4">
            {text.trim() ? (
              <div className={bubble}>{text}</div>
            ) : (
              <div className="max-w-[82%] rounded-2xl rounded-tl-md bg-neutral-800/50 px-3 py-2 text-sm italic text-neutral-500">
                Sua mensagem aparece aqui…
              </div>
            )}

            {validButtons.length > 0 && <Buttons buttons={validButtons} />}

            {/* Mensagens seguintes do flow, empilhadas */}
            {rest.map((m) => {
              const t = (m.text ?? "").trim();
              const bts = (m.buttons ?? []).filter((b) => b.label.trim() || b.url.trim());
              if (!t && !bts.length) return null;
              return (
                <div key={m.id} className="space-y-2">
                  {t && <div className={bubble}>{t}</div>}
                  {bts.length > 0 && <Buttons buttons={bts} />}
                </div>
              );
            })}
          </div>

          {/* Barra de digitar */}
          <div className="flex items-center gap-2 px-3 pb-2 pt-1">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-neutral-800 text-neutral-400">
              <Camera size={15} />
            </span>
            <div className="flex-1 rounded-full border border-neutral-700 px-3 py-1.5 text-xs text-neutral-500">
              Mensagem…
            </div>
          </div>

          {/* Home indicator */}
          <div className="flex justify-center pb-2">
            <div className="h-1 w-24 rounded-full bg-neutral-600" />
          </div>
        </div>
      </div>
    </div>
  );
}
