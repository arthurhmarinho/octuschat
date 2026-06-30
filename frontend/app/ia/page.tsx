import { Sparkles } from "lucide-react";
import AppShell from "@/components/AppShell";

export default function IaPage() {
  return (
    <AppShell title="IA">
      <div className="glass flex flex-col items-center justify-center px-6 py-20 text-center">
        <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--gold)]/10 text-[var(--gold)]">
          <Sparkles size={26} />
        </span>
        <h3 className="text-lg font-semibold">Respostas com IA</h3>
        <p className="mt-1 max-w-sm text-sm text-[var(--muted)]">
          Em breve: deixe a IA responder DMs e recomendar produtos automaticamente.
        </p>
      </div>
    </AppShell>
  );
}
