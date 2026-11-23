import type { ComponentType } from "react";
import { cx } from "./cx";

type Option<T extends string> = {
  value: T;
  label: string;
  icon?: ComponentType<{ size?: number; strokeWidth?: number }>;
};

/** Controle segmentado (rádio visual) — seleção = `raised` + inset, como o nav. */
export default function Segmented<T extends string>({
  value,
  onChange,
  options,
  "aria-label": ariaLabel,
}: {
  value: T;
  onChange: (v: T) => void;
  options: Option<T>[];
  "aria-label": string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className="grid gap-0.5 rounded-control border border-line bg-bg-deep p-0.5"
      style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
    >
      {options.map(({ value: v, label, icon: Icon }) => {
        const active = v === value;
        return (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(v)}
            className={cx(
              "flex h-8 items-center justify-center gap-2 rounded-[6px] text-[13px]",
              "transition-[background-color,color] duration-150 ease-out",
              active
                ? "bg-raised font-medium text-fg shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]"
                : "text-fg-2 hover:text-fg"
            )}
          >
            {Icon && <Icon size={16} strokeWidth={1.5} />}
            {label}
          </button>
        );
      })}
    </div>
  );
}
