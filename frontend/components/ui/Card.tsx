import type { HTMLAttributes } from "react";
import { cx } from "./cx";

export default function Card({
  padding = "md",
  className,
  ...rest
}: { padding?: "md" | "none" } & HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx(
        "rounded-card border border-line bg-card",
        padding === "md" && "p-5",
        className
      )}
      {...rest}
    />
  );
}
