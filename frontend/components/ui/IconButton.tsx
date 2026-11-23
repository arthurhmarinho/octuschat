import type { ButtonHTMLAttributes, ComponentType } from "react";
import { cx } from "./cx";

type Props = {
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
  "aria-label": string;
  tone?: "default" | "danger";
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children">;

export default function IconButton({
  icon: Icon,
  tone = "default",
  className,
  type = "button",
  ...rest
}: Props) {
  return (
    <button
      type={type}
      className={cx(
        "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-control text-fg-3",
        // Toque: alvo de 44px em telas sem ponteiro fino.
        "[@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:w-11",
        "transition-[background-color,color,transform] duration-150 ease-out",
        "active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50",
        tone === "danger"
          ? "hover:bg-negative/10 hover:text-negative"
          : "hover:bg-raised hover:text-fg",
        className
      )}
      {...rest}
    >
      <Icon size={16} strokeWidth={1.5} />
    </button>
  );
}
