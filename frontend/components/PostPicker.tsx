"use client";

import { useEffect, useState } from "react";
import { Check, Image as ImageIcon } from "lucide-react";

type Media = {
  id: string;
  caption?: string;
  media_type?: string;
  media_url?: string;
  thumbnail_url?: string;
  permalink?: string;
};

type State = "loading" | "ready" | "empty";

export default function PostPicker({
  accountId,
  value,
  onChange,
}: {
  accountId: string;
  value: string;
  onChange: (postId: string) => void;
}) {
  const [media, setMedia] = useState<Media[]>([]);
  const [state, setState] = useState<State>("loading");

  useEffect(() => {
    let alive = true;
    fetch(`/api/backend/instagram/${accountId}/media`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: Media[]) => {
        if (!alive) return;
        if (Array.isArray(data) && data.length) {
          setMedia(data);
          setState("ready");
        } else {
          setState("empty");
        }
      })
      .catch(() => alive && setState("empty"));
    return () => {
      alive = false;
    };
  }, [accountId]);

  if (state === "loading") {
    return <p className="text-sm text-[var(--muted)]">Carregando publicações…</p>;
  }

  if (state === "empty") {
    return (
      <div className="rounded-lg border border-dashed border-[var(--border)] p-4">
        <p className="flex items-center gap-2 text-sm text-[var(--muted)]">
          <ImageIcon size={15} />
          Nenhuma publicação carregada. Quando o Instagram estiver conectado, suas
          publicações aparecem aqui em grade para você clicar e escolher.
        </p>
        <label className="mono mb-1.5 mt-3 block text-xs uppercase tracking-wide text-[var(--muted)]">
          ID da publicação (manual, por enquanto)
        </label>
        <input
          className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3.5 py-2.5 text-sm outline-none transition-colors focus:border-[var(--gold)]"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Ex.: 17912345678901234"
        />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-3 gap-2">
      {media.map((m) => {
        const selected = m.id === value;
        const thumb = m.thumbnail_url || m.media_url;
        return (
          <button
            key={m.id}
            type="button"
            onClick={() => onChange(m.id)}
            className={`relative aspect-square overflow-hidden rounded-lg border ${
              selected ? "border-[var(--gold)] ring-2 ring-[var(--gold)]/40" : "border-[var(--border)]"
            }`}
          >
            {thumb ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={thumb} alt={m.caption || "post"} className="h-full w-full object-cover" />
            ) : (
              <span className="flex h-full w-full items-center justify-center bg-white/5 text-[var(--muted)]">
                <ImageIcon size={18} />
              </span>
            )}
            {selected && (
              <span className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--gold)] text-[#2a1e05]">
                <Check size={12} />
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
