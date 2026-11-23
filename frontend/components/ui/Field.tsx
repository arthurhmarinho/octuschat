import type { ReactNode } from "react";

export default function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
}: {
  label: string;
  htmlFor?: string;
  hint?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-2 block text-[13px] font-medium text-fg-2">
        {label}
      </label>
      {children}
      {error ? (
        <p className="mt-2 text-xs text-negative">{error}</p>
      ) : hint ? (
        <p className="mt-2 text-xs text-fg-3">{hint}</p>
      ) : null}
    </div>
  );
}
