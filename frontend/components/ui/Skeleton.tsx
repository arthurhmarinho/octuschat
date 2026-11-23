import { cx } from "./cx";

/** Bloco cinza pulsante. Decorativo: quem usa marca a região com aria-busy. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cx("animate-pulse rounded-control bg-raised motion-reduce:animate-none", className)}
    />
  );
}

/** Linhas de lista: avatar + duas linhas de texto. Mesma altura das linhas reais (h-16). */
export function SkeletonRows({ rows = 5, avatar = true }: { rows?: number; avatar?: boolean }) {
  return (
    <div aria-busy="true" aria-label="Carregando">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex h-16 items-center gap-3 border-b border-line px-4 last:border-b-0">
          {avatar && <Skeleton className="h-8 w-8 shrink-0 rounded-full" />}
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-40" />
            <Skeleton className="h-3 w-64 max-w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}
