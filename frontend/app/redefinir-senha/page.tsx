"use client";

import { useState, type FormEvent } from "react";
import AuthCard from "@/components/AuthCard";
import InviteGate from "@/components/InviteGate";
import NewPasswordFields, { passwordReady } from "@/components/NewPasswordFields";
import { Button } from "@/components/ui";
import { useInvite, type InviteInfo } from "@/lib/invite";

function ResetForm({
  token,
  invite,
  onGone,
}: {
  token: string;
  invite: InviteInfo;
  onGone: () => void;
}) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const ready = passwordReady(password, confirm);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!ready) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      });
      if (res.ok) {
        window.location.replace("/");
        return;
      }
      if (res.status === 410) return onGone();
      const data = await res.json().catch(() => ({}));
      setError(data.detail || "Não foi possível alterar a senha");
    } catch {
      setError("Não foi possível alterar a senha. Verifique a conexão");
    }
    setSaving(false);
  }

  return (
    <form onSubmit={onSubmit}>
      <p className="mb-4 break-words text-[13px] text-fg-2">
        Conta <span className="text-fg">{invite.email}</span>
      </p>
      {/* Ajuda o gerenciador de senhas a ligar a senha nova a esta conta. */}
      <input type="email" autoComplete="username" value={invite.email ?? ""} readOnly hidden />
      <div className="space-y-4">
        <NewPasswordFields
          label="Nova senha"
          password={password}
          confirm={confirm}
          onPassword={setPassword}
          onConfirm={setConfirm}
        />
      </div>
      {error && (
        <p role="alert" className="mt-3 text-[13px] text-negative">
          {error}
        </p>
      )}
      <Button type="submit" variant="primary" disabled={!ready || saving} className="mt-5 w-full">
        {saving ? "Salvando" : "Salvar e entrar"}
      </Button>
    </form>
  );
}

export default function RedefinirSenhaPage() {
  const { state, reload, expire } = useInvite("reset");

  return (
    <AuthCard title="Defina uma nova senha">
      <InviteGate state={state} onRetry={reload}>
        {({ token, invite }) => <ResetForm token={token} invite={invite} onGone={expire} />}
      </InviteGate>
    </AuthCard>
  );
}
