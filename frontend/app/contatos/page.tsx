"use client";

import { useEffect, useState } from "react";
import { Users } from "lucide-react";
import AppShell from "@/components/AppShell";
import Avatar from "@/components/Avatar";
import { Card, EmptyState, Note, Spinner } from "@/components/ui";
import { useAccount } from "@/lib/account";
import { formatDateTime } from "@/lib/format";

type Contact = {
  id: number;
  ig_user_id: string;
  username: string | null;
  profile_pic: string | null;
  first_seen: string;
  last_message_at: string | null;
};

export default function ContatosPage() {
  const { accountId, resolved } = useAccount();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!resolved) return;
    if (!accountId) {
      setLoading(false);
      return;
    }
    fetch(`/api/backend/contacts?account_id=${accountId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: Contact[]) => setContacts(data))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [accountId, resolved]);

  const count = (
    <span className="font-mono text-xs text-fg-3">
      {contacts.length} {contacts.length === 1 ? "contato" : "contatos"}
    </span>
  );

  return (
    <AppShell title="Contatos" action={!loading && contacts.length > 0 ? count : undefined}>
      {loading && (
        <div className="flex justify-center py-24">
          <Spinner />
        </div>
      )}

      {!loading && error && (
        <Note variant="warning">
          Não foi possível carregar seus contatos. Verifique a conexão e tente de novo
        </Note>
      )}

      {!loading && !error && contacts.length === 0 && (
        <Card padding="none">
          <EmptyState
            icon={Users}
            title="Nenhum contato ainda"
            description="Quem comentar ou mandar DM vira contato automaticamente"
          />
        </Card>
      )}

      {!loading && !error && contacts.length > 0 && (
        <Card padding="none" className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="h-9 border-b border-line text-left text-xs text-fg-3">
                <th className="px-5 font-normal">Contato</th>
                <th className="px-5 font-normal">ID do Instagram</th>
                <th className="px-5 text-right font-normal">Primeiro contato</th>
                <th className="px-5 text-right font-normal">Última mensagem</th>
              </tr>
            </thead>
            <tbody>
              {contacts.map((c) => (
                <tr key={c.id} className="h-12 border-b border-line last:border-b-0">
                  <td className="px-5">
                    <div className="flex items-center gap-3">
                      <Avatar src={c.profile_pic} name={c.username || c.ig_user_id} size={28} />
                      <span className="text-sm text-fg">
                        {c.username ? `@${c.username}` : `usuário ${c.ig_user_id}`}
                      </span>
                    </div>
                  </td>
                  <td className="px-5 font-mono text-xs text-fg-3">{c.ig_user_id}</td>
                  <td className="px-5 text-right font-mono text-xs text-fg-3">
                    {formatDateTime(c.first_seen)}
                  </td>
                  <td className="px-5 text-right font-mono text-xs text-fg-3">
                    {formatDateTime(c.last_message_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </AppShell>
  );
}
