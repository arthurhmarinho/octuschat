"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Search, Users, X } from "lucide-react";
import AppShell from "@/components/AppShell";
import Avatar from "@/components/Avatar";
import { Card, EmptyState, IconButton, Input, Note, SkeletonRows } from "@/components/ui";
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
  const [query, setQuery] = useState("");

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

  const shown = useMemo(() => {
    const q = query.trim().replace(/^@/, "").toLowerCase();
    if (!q) return contacts;
    return contacts.filter(
      (c) => (c.username ?? "").toLowerCase().includes(q) || c.ig_user_id.includes(q)
    );
  }, [contacts, query]);

  const count = (
    <span className="font-mono text-xs text-fg-3">
      {query.trim() && shown.length !== contacts.length
        ? `${shown.length} de ${contacts.length}`
        : `${contacts.length} ${contacts.length === 1 ? "contato" : "contatos"}`}
    </span>
  );

  return (
    <AppShell title="Contatos" action={!loading && contacts.length > 0 ? count : undefined}>
      {loading && (
        <Card padding="none">
          <SkeletonRows rows={6} />
        </Card>
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
        <div className="space-y-4">
          <div className="relative max-w-sm">
            <Search
              size={16}
              strokeWidth={1.5}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fg-3"
            />
            <Input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar contato"
              aria-label="Buscar contato por usuário ou ID"
              className="px-9 [&::-webkit-search-cancel-button]:hidden"
            />
            {query && (
              <IconButton
                icon={X}
                aria-label="Limpar busca"
                onClick={() => setQuery("")}
                className="absolute right-1 top-1/2 -translate-y-1/2"
              />
            )}
          </div>

          {shown.length === 0 ? (
            <Card padding="none">
              <EmptyState
                icon={Search}
                title="Nenhum contato encontrado"
                description={`Nada corresponde a "${query.trim()}"`}
              />
            </Card>
          ) : (
            <Card padding="none" className="overflow-x-auto">
              <table className="w-full min-w-[640px] table-fixed text-sm">
                <colgroup>
                  <col className="w-[34%]" />
                  <col className="w-[22%]" />
                  <col />
                  <col />
                </colgroup>
                <thead>
                  <tr className="h-9 border-b border-line text-left text-xs text-fg-3">
                    <th className="px-5 font-normal">Contato</th>
                    <th className="px-5 font-normal">ID do Instagram</th>
                    <th className="px-5 text-right font-normal">Primeiro contato</th>
                    <th className="px-5 text-right font-normal">Última mensagem</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((c) => (
                    <tr
                      key={c.id}
                      className="relative h-12 border-b border-line transition-colors duration-150 ease-out last:border-b-0 hover:bg-raised/40"
                    >
                      <td className="px-5">
                        <div className="flex items-center gap-3">
                          <Avatar src={c.profile_pic} name={c.username || c.ig_user_id} size={28} />
                          {/* Link esticado: a linha abre a conversa com este contato */}
                          <Link
                            href={`/conversas?c=${c.id}`}
                            className="rounded-sm text-sm text-fg after:absolute after:inset-0 after:content-['']"
                          >
                            {c.username ? `@${c.username}` : `usuário ${c.ig_user_id}`}
                          </Link>
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
        </div>
      )}
    </AppShell>
  );
}
