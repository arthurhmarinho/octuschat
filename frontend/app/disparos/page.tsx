"use client";

import { useEffect, useState } from "react";
import { Send, Info } from "lucide-react";
import AppShell from "@/components/AppShell";
import { useAccount } from "@/lib/account";

export default function DisparosPage() {
  const { accountId, resolved } = useAccount();
  const [count, setCount] = useState<number | null>(null);
  const [text, setText] = useState("");

  useEffect(() => {
    if (!resolved) return;
    if (!accountId) {
      setCount(0);
      return;
    }
    fetch(`/api/backend/contacts?account_id=${accountId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: unknown[]) => setCount(data.length))
      .catch(() => setCount(0));
  }, [accountId, resolved]);

  return (
    <AppShell title="Disparos">
      <div className="mx-auto max-w-2xl">
        <p className="mb-6 text-sm text-[var(--muted)]">
          Envie uma mensagem para os seus contatos de uma vez (broadcast).
        </p>

        <div className="glass space-y-4 p-6">
          <div>
            <label className="mono mb-1.5 block text-xs uppercase tracking-wide text-[var(--muted)]">
              Mensagem
            </label>
            <textarea
              className="min-h-[120px] w-full resize-y rounded-lg border border-[var(--border)] bg-black/30 px-3.5 py-2.5 text-sm outline-none focus:border-[var(--gold)]"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Escreva o disparo…"
            />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm text-[var(--muted)]">
              {count === null ? "…" : count} destinatário{count === 1 ? "" : "s"}
            </span>
            <button
              disabled
              title="Disponível quando o Instagram estiver conectado"
              className="btn-gold inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm opacity-50"
            >
              <Send size={16} /> Disparar
            </button>
          </div>

          <div className="flex items-start gap-2 rounded-lg border border-[var(--border)] bg-black/20 p-3 text-xs text-[var(--muted)]">
            <Info size={15} className="mt-0.5 shrink-0" />
            <span>
              O envio real ativa quando o Instagram estiver conectado. A Meta só permite
              DMs dentro da janela de mensagens (24h após a última interação do contato),
              então broadcasts respeitam essa regra.
            </span>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
