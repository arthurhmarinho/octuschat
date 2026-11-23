import { Loader2 } from "lucide-react";
import { cx } from "./cx";

export default function Spinner({ className }: { className?: string }) {
  return (
    <Loader2
      size={16}
      strokeWidth={1.5}
      className={cx("animate-spin text-fg-3", className)}
      aria-label="Carregando"
    />
  );
}
