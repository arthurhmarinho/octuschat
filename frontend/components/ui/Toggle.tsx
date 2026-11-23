import { cx } from "./cx";

export default function Toggle({
  checked,
  onChange,
  disabled,
  "aria-label": ariaLabel,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  "aria-label": string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cx(
        "relative h-[18px] w-8 shrink-0 rounded-full border transition-colors duration-150 ease-out",
        "disabled:opacity-50",
        checked ? "border-fg bg-fg" : "border-line bg-raised"
      )}
    >
      <span
        className={cx(
          "absolute left-[2px] top-[2px] h-3 w-3 rounded-full transition-[transform,background-color] duration-150 ease-out",
          checked ? "translate-x-[14px] bg-on-fg" : "translate-x-0 bg-fg-3"
        )}
      />
    </button>
  );
}
