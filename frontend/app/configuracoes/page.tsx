import { Settings } from "lucide-react";
import AppShell from "@/components/AppShell";

export default function ConfiguracoesPage() {
  return (
    <AppShell title="Configurações">
      <div className="glass flex flex-col items-center justify-center px-6 py-20 text-center">
        <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--gold)]/10 text-[var(--gold)]">
          <Settings size={26} />
        </span>
        <h3 className="text-lg font-semibold">Configurações</h3>
        <p className="mt-1 max-w-sm text-sm text-[var(--muted)]">
          Em breve: conta conectada, token da Meta, preferências da automação.
        </p>
      </div>
    </AppShell>
  );
}
