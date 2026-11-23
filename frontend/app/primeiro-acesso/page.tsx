"use client";

import { useEffect, useRef } from "react";
import PasswordForm from "@/components/PasswordForm";
import { Card } from "@/components/ui";
import { useUser } from "@/lib/user";

/** Convite novo: a senha temporária precisa ser trocada antes de usar o painel. */
export default function PrimeiroAcessoPage() {
  const { user, resolved } = useUser();
  const finishing = useRef(false);

  // Quem já trocou a senha não tem o que fazer aqui. (Não vale logo depois de
  // trocar: aí o destino é /configuracoes, definido abaixo.)
  useEffect(() => {
    if (finishing.current) return;
    if (resolved && user && !user.must_change_password) window.location.replace("/");
  }, [resolved, user]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-4">
      <Card padding="none" className="w-full max-w-[400px] rounded-panel p-6">
        <h1 className="text-base font-medium text-fg">Defina sua senha</h1>
        <p className="mb-6 mt-1 text-[13px] text-fg-2">
          {user ? `${user.name}, ` : ""}a senha que você recebeu é temporária. Escolha uma nova para continuar
        </p>
        <PasswordForm
          submitLabel="Salvar e continuar"
          onDone={() => {
            finishing.current = true;
            window.location.replace("/configuracoes");
          }}
        />
      </Card>
    </main>
  );
}
