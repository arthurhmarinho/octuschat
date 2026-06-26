"use client";

import { Instagram } from "lucide-react";

type Props = {
  username: string;
  text: string;
  linkUrl?: string;
  linkLabel?: string;
};

/**
 * Mock de uma conversa de DM do Instagram, usado no preview ao vivo.
 * Mostra o texto como balão recebido e, se houver link, um "card" clicável
 * imitando o preview de link do Instagram.
 */
export default function DmPreview({ username, text, linkUrl, linkLabel }: Props) {
  return (
    <div className="mx-auto w-full max-w-[320px] rounded-[2rem] border border-neutral-700 bg-black p-3 shadow-xl">
      {/* Header da conversa */}
      <div className="flex items-center gap-3 border-b border-neutral-800 pb-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-tr from-yellow-400 via-pink-500 to-purple-600">
          <Instagram size={18} className="text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold leading-tight">
            {username || "sua_conta"}
          </p>
          <p className="text-xs text-neutral-500">Instagram</p>
        </div>
      </div>

      {/* Corpo da conversa */}
      <div className="min-h-[180px] space-y-2 py-4">
        {text.trim() ? (
          <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-tl-sm bg-neutral-800 px-3 py-2 text-sm">
            {text}
          </div>
        ) : (
          <div className="max-w-[80%] rounded-2xl rounded-tl-sm bg-neutral-800/50 px-3 py-2 text-sm italic text-neutral-500">
            Sua mensagem aparece aqui…
          </div>
        )}

        {linkUrl && (
          <a
            href={linkUrl}
            target="_blank"
            rel="noreferrer"
            className="block max-w-[80%] overflow-hidden rounded-2xl border border-neutral-700 bg-neutral-900"
          >
            <div className="flex h-20 items-center justify-center bg-neutral-800 text-neutral-500">
              🔗
            </div>
            <div className="px-3 py-2">
              <p className="truncate text-sm font-medium text-blue-400">
                {linkLabel || "Abrir link"}
              </p>
              <p className="truncate text-xs text-neutral-500">{linkUrl}</p>
            </div>
          </a>
        )}
      </div>
    </div>
  );
}
