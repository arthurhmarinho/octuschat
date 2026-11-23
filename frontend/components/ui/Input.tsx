import type {
  ComponentProps,
  InputHTMLAttributes,
  SelectHTMLAttributes,
} from "react";
import { cx } from "./cx";

/** Única string de estilo de controle de formulário. */
export const controlCls =
  "w-full rounded-control border border-line bg-raised px-3 text-sm text-fg " +
  "placeholder:text-fg-3 outline-none transition-[border-color,box-shadow] duration-150 ease-out " +
  "focus:border-line-strong focus:ring-2 focus:ring-fg/10 disabled:opacity-50";

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cx(controlCls, "h-9", className)} {...rest} />;
}

export function Textarea({
  className,
  rows = 3,
  ...rest
}: ComponentProps<"textarea">) {
  return (
    <textarea
      rows={rows}
      className={cx(controlCls, "resize-none py-2 leading-5", className)}
      {...rest}
    />
  );
}

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cx(controlCls, "h-9", className)} {...rest}>
      {children}
    </select>
  );
}
