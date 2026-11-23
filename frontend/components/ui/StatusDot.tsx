import { cx } from "./cx";

export default function StatusDot({
  tone = "neutral",
  className,
}: {
  tone?: "positive" | "neutral" | "negative";
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cx(
        "inline-block h-1.5 w-1.5 shrink-0 rounded-full",
        tone === "positive" && "bg-positive",
        tone === "negative" && "bg-negative",
        tone === "neutral" && "bg-fg-3",
        className
      )}
    />
  );
}
