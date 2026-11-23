"use client";

import AppShell from "@/components/AppShell";
import Avatar from "@/components/Avatar";
import ConnectNotice from "@/components/ConnectNotice";
import { Button, Card, Spinner, StatusDot } from "@/components/ui";
import { useAccount } from "@/lib/account";
import { formatDateTime } from "@/lib/format";

export default function ConfiguracoesPage() {
  const { account, resolved } = useAccount();
  const connected = account && account.ig_user_id !== "demo" ? account : null;

  return (
    <AppShell title="Configurações">
      <div className="max-w-2xl">
        <ConnectNotice />

        <Card>
          <h2 className="text-[15px] font-medium text-fg">Conta do Instagram</h2>

          {!resolved ? (
            <div className="py-6">
              <Spinner />
            </div>
          ) : connected ? (
            <>
              <div className="my-4 flex items-center gap-3">
                <Avatar name={connected.username ?? connected.ig_user_id} size={40} />
                <div>
                  <p className="flex items-center gap-2 text-sm font-medium text-fg">
                    {connected.username ? `@${connected.username}` : connected.ig_user_id}
                    <StatusDot tone="positive" />
                  </p>
                  <p className="text-[13px] text-fg-2">
                    Conectada em {formatDateTime(connected.connected_at)}
                  </p>
                </div>
              </div>
              {/* Link comum: o proxy responde com redirect para a Meta. */}
              <Button variant="secondary" href="/api/backend/instagram/connect">
                Reconectar Instagram
              </Button>
            </>
          ) : (
            <>
              <p className="mb-4 mt-1 text-sm text-fg-2">
                Conecte uma conta profissional para ativar suas automações
              </p>
              <Button variant="primary" href="/api/backend/instagram/connect">
                Conectar Instagram
              </Button>
            </>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
