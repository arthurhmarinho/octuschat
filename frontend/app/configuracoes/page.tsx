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
        {/* Link comum (não <Link>): o proxy responde com redirect para a Meta. */}
        <a
          href="/api/backend/instagram/connect"
          className="btn-gold mt-6 rounded-lg px-4 py-2.5 text-sm"
        >
          Conectar Instagram
        </a>
      </div>
    </AppShell>
  );
}
