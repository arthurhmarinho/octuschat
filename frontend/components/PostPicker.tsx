"use client";

import { useEffect, useState } from "react";
import { Check, Image as ImageIcon } from "lucide-react";
import { Field, Input, Spinner, cx } from "@/components/ui";

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
    return (
      <div className="flex items-center gap-2 text-[13px] text-fg-2">
        <Spinner /> Carregando publicações
      </div>
    );
  }

  if (state === "empty") {
    return (
      <Field
        label="ID da publicação"
        htmlFor="post-id"
        hint="Não foi possível carregar suas publicações. Cole o ID de uma publicação para continuar"
      >
        <Input
          id="post-id"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="17912345678901234"
        />
      </Field>
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
            aria-pressed={selected}
            className={cx(
              "relative aspect-square overflow-hidden rounded-control bg-raised",
              "transition-[box-shadow] duration-150 ease-out",
              selected ? "ring-2 ring-fg" : "ring-1 ring-line hover:ring-line-strong"
            )}
          >
            {thumb ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={thumb} alt={m.caption || "Publicação"} className="h-full w-full object-cover" />
            ) : (
              <span className="flex h-full w-full items-center justify-center text-fg-3">
                <ImageIcon size={16} strokeWidth={1.5} />
              </span>
            )}
            {selected && (
              <span className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-fg text-on-fg">
                <Check size={12} strokeWidth={2} />
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
