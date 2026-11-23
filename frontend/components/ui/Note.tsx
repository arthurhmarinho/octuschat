import { Info, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "./cx";

export default function Note({
  variant = "info",
  children,
  className,
}: {
  variant?: "info" | "warning";
  children: ReactNode;
  className?: string;
}) {
  const Icon = variant === "warning" ? TriangleAlert : Info;
  return (
    <div
      className={cx(
        "flex items-start gap-2.5 rounded-control border border-line bg-raised/50 p-3",
        className
      )}
    >
      <Icon
        size={16}
        strokeWidth={1.5}
        className={cx("mt-0.5 shrink-0", variant === "warning" ? "text-warning" : "text-fg-3")}
      />
      <div className="text-[13px] leading-5 text-fg-2">{children}</div>
    </div>
  );
}
