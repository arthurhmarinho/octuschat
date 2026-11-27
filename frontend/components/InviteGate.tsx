import type { ReactNode } from "react";
import { Button, Spinner } from "@/components/ui";
import type { InviteState } from "@/lib/invite";

/** Estados de um link antes do formulário: conferindo, sem rede e inválido. */
export default function InviteGate({
  state,
  onRetry,
  children,
}: {
  state: InviteState;
  onRetry: () => void;
  children: (ok: Extract<InviteState, { status: "ok" }>) => ReactNode;
}) {
  if (state.status === "ok") return <>{children(state)}</>;
  if (state.status === "loading") {
    return (
      <div className="flex justify-center py-6">
        <Spinner />
      </div>
    );
  }
  if (state.status === "error") {
    return (
      <>
        <p role="alert" className="text-[13px] text-fg-2">
          Não foi possível conferir o convite. Verifique a conexão
        </p>
        <Button variant="primary" onClick={onRetry} className="mt-5 w-full">
          Tentar de novo
        </Button>
      </>
    );
  }
  return (
    <>
      <p role="alert" className="text-[13px] leading-5 text-fg-2">
        Este convite não vale mais. Peça um novo a quem te convidou
      </p>
      <Button variant="secondary" href="/login" className="mt-5 w-full">
        Ir para o login
      </Button>
    </>
  );
}
