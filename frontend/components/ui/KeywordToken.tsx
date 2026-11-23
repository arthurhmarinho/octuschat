import { cx } from "./cx";

/** Assinatura do produto: a palavra-chave como a pessoa digitaria no comentário. */
export function KeywordToken({ children, className }: { children: string; className?: string }) {
  return (
    <span
      className={cx(
        "inline-flex h-5 items-center rounded-sm border border-line-strong px-1.5",
        "font-mono text-xs uppercase leading-none text-fg",
        className
      )}
    >
      {children}
    </span>
  );
}

/** Lista de tokens a partir de "preço, valor" (separados por vírgula). */
export function KeywordTokens({
  value,
  className,
}: {
  value: string | null | undefined;
  className?: string;
}) {
  const words = (value ?? "")
    .split(",")
    .map((w) => w.trim())
    .filter(Boolean);
  if (!words.length) return null;
  return (
    <span className={cx("inline-flex flex-wrap items-center gap-1", className)}>
      {words.map((w) => (
        <KeywordToken key={w}>{w}</KeywordToken>
      ))}
    </span>
  );
}
