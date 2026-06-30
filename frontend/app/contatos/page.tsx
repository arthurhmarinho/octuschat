"use client";

import { useEffect, useState } from "react";
import { Users } from "lucide-react";
import AppShell from "@/components/AppShell";
import { useAccount } from "@/lib/account";

type Contact = {
  id: number;
  ig_user_id: string;
  username: string | null;
  first_seen: string;
  last_message_at: string | null;
};

export default function ContatosPage() {
  const { accountId, resolved } = useAccount();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!resolved) return;
    if (!accountId) {
      setLoading(false);
      return;
    }
    fetch(`/api/backend/contacts?account_id=${accountId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: Contact[]) => setContacts(data))
      .catch(() => setContacts([]))
      .finally(() => setLoading(false));
  }, [accountId, resolved]);

  const fmt = (d: string | null) => (d ? new Date(d).toLocaleString("pt-BR") : "—");

  if (!loading && contacts.length === 0) {
    return (
      <AppShell title="Contatos">
        <div className="glass flex flex-col items-center justify-center px-6 py-20 text-center">
          <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--gold)]/10 text-[var(--gold)]">
            <Users size={26} />
          </span>
          <h3 className="text-lg font-semibold">Nenhum contato ainda</h3>
          <p className="mt-1 max-w-sm text-sm text-[var(--muted)]">
            Pessoas que comentarem ou enviarem DM viram contatos automaticamente.
            Conecte o Instagram para começar a capturar.
          </p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title="Contatos">
      <div className="mb-4 text-sm text-[var(--muted)]">
        {contacts.length} contato{contacts.length === 1 ? "" : "s"}
      </div>
      <div className="glass overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
              <th className="px-5 py-3 font-medium">Contato</th>
              <th className="px-5 py-3 font-medium">IGSID</th>
              <th className="px-5 py-3 font-medium">Primeiro contato</th>
              <th className="px-5 py-3 font-medium">Última mensagem</th>
            </tr>
          </thead>
          <tbody>
            {contacts.map((c) => (
              <tr key={c.id} className="border-b border-[var(--border)] last:border-0">
                <td className="px-5 py-3">
                  <div className="flex items-center gap-3">
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-tr from-yellow-400 via-pink-500 to-purple-600 text-xs font-bold text-white">
                      {(c.username || c.ig_user_id).charAt(0).toUpperCase()}
                    </span>
                    <span className="font-medium">{c.username || `usuário ${c.ig_user_id}`}</span>
                  </div>
                </td>
                <td className="mono px-5 py-3 text-[var(--muted)]">{c.ig_user_id}</td>
                <td className="px-5 py-3 text-[var(--muted)]">{fmt(c.first_seen)}</td>
                <td className="px-5 py-3 text-[var(--muted)]">{fmt(c.last_message_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
