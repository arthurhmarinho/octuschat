"use client";

import AppShell from "@/components/AppShell";
import Avatar from "@/components/Avatar";
import ConnectNotice from "@/components/ConnectNotice";
import PasswordForm from "@/components/PasswordForm";
import PeopleCard from "@/components/PeopleCard";
import { Button, Card, Note, Spinner, StatusDot } from "@/components/ui";
import { useAccount } from "@/lib/account";
import { formatDateTime } from "@/lib/format";
import { useUser } from "@/lib/user";

const CONNECT = "/api/backend/instagram/connect";

export default function ConfiguracoesPage() {
  const { accounts, resolved } = useAccount();
  const { user } = useUser();

  return (
    <AppShell title="Configurações">
      <div className="max-w-2xl space-y-4">
        <ConnectNotice />

        {/* ── Sua conta ── */}
        <Card>
          <h2 className="text-[15px] font-medium text-fg">Sua conta</h2>
          {user ? (
            <dl className="mt-4 grid grid-cols-[88px_1fr] gap-y-2 text-sm">
              <dt className="text-fg-3">Nome</dt>
              <dd className="text-fg">{user.name}</dd>
              <dt className="text-fg-3">E-mail</dt>
              <dd className="text-fg">{user.email}</dd>
            </dl>
          ) : (
            <div className="py-6"><Spinner /></div>
          )}
          <div className="mt-6 border-t border-line pt-5">
            <h3 className="mb-4 text-[13px] font-medium text-fg-2">Alterar senha</h3>
            <div className="max-w-sm">
              <PasswordForm />
            </div>
          </div>
        </Card>

        {/* ── Instagram ── */}
        <Card>
          <h2 className="text-[15px] font-medium text-fg">Instagram</h2>

          {!resolved ? (
            <div className="py-6"><Spinner /></div>
          ) : accounts.length === 0 ? (
            <>
              <p className="mb-4 mt-1 text-sm text-fg-2">
                Conecte uma conta profissional para ativar suas automações
              </p>
              <Button variant="primary" href={CONNECT}>
                Conectar Instagram
              </Button>
            </>
          ) : (
            <>
              <ul className="mt-4 divide-y divide-line">
                {accounts.map((a) => (
                  <li key={a.ig_user_id} className="flex flex-wrap items-center gap-3 py-3 first:pt-0">
                    <Avatar name={a.username ?? a.ig_user_id} size={40} />
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-2 text-sm font-medium text-fg">
                        <span className="truncate">{a.username ? `@${a.username}` : a.ig_user_id}</span>
                        <StatusDot tone={a.needs_reconnect ? "negative" : "positive"} />
                      </p>
                      <p className="text-[13px] text-fg-2">
                        {a.needs_reconnect
                          ? "A Meta recusou o acesso desta conta"
                          : `Conectada em ${formatDateTime(a.connected_at)}`}
                      </p>
                    </div>
                    {/* Link comum: o proxy responde com redirect para a Meta. */}
                    <Button
                      variant={a.needs_reconnect ? "primary" : "secondary"}
                      size="sm"
                      href={CONNECT}
                    >
                      Reconectar
                    </Button>
                  </li>
                ))}
              </ul>
              {accounts.some((a) => a.needs_reconnect) && (
                <Note variant="warning" className="mt-4">
                  O acesso expirou ou foi revogado no Instagram. Reconecte para as automações
                  voltarem a responder
                </Note>
              )}
              <div className="mt-4 border-t border-line pt-4">
                <Button variant="ghost" size="sm" href={CONNECT}>
                  Conectar outra conta
                </Button>
              </div>
            </>
          )}
        </Card>

        {user?.is_admin && <PeopleCard />}
      </div>
    </AppShell>
  );
}
