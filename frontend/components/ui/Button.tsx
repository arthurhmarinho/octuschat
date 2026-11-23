import Link from "next/link";
import type { ButtonHTMLAttributes, ComponentType, ReactNode } from "react";
import { cx } from "./cx";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const VARIANT: Record<Variant, string> = {
  primary:
    "bg-fg text-on-fg shadow-[inset_0_1px_0_rgba(255,255,255,0.12)] hover:bg-fg/90",
  secondary:
    "bg-raised text-fg border border-line hover:border-line-strong",
  ghost: "text-fg-2 hover:bg-raised hover:text-fg",
  danger: "text-negative hover:bg-negative/10",
};

const SIZE: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px]",
  md: "h-9 px-4 text-sm",
};

type Props = {
  variant?: Variant;
  size?: Size;
  icon?: ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;
  href?: string;
  className?: string;
  children?: ReactNode;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "children">;

export default function Button({
  variant = "secondary",
  size = "md",
  icon: Icon,
  href,
  className,
  children,
  type = "button",
  ...rest
}: Props) {
  const cls = cx(
    "inline-flex shrink-0 items-center justify-center gap-2 rounded-control font-medium",
    "transition-[background-color,border-color,color,transform] duration-150 ease-out",
    "active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50",
    VARIANT[variant],
    SIZE[size],
    className
  );
  const content = (
    <>
      {Icon && <Icon size={16} strokeWidth={1.5} />}
      {children}
    </>
  );
  if (href && !rest.disabled) {
    return (
      <Link href={href} className={cls}>
        {content}
      </Link>
    );
  }
  return (
    <button type={type} className={cls} {...rest}>
      {content}
    </button>
  );
}
