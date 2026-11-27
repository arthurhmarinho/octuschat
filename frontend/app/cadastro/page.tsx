"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import AuthCard from "@/components/AuthCard";
import InviteGate from "@/components/InviteGate";
import NewPasswordFields, { passwordReady } from "@/components/NewPasswordFields";
import { Button, Field, Input, Spinner } from "@/components/ui";
import { useInvite, type InviteInfo } from "@/lib/invite";
import type { User } from "@/lib/user";

function SignupForm({
  token,
  invite,
  onGone,
}: {
  token: string;
  invite: InviteInfo;
  onGone: () => void;
}) {
  const [name, setName] = useState(invite.name ?? "");
  const [email, setEmail] = useState(invite.email ?? "");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<{ text: string; taken: boolean } | null>(null);
  const [saving, setSaving] = useState(false);

  const ready = !!name.trim() && !!email.trim() && passwordReady(password, confirm);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!ready) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, name, email, password }),
      });
      if (res.ok) {
        window.location.replace("/conectar");
        return;
      }
      if (res.status === 410) return onGone();
      const data = await res.json().catch(() => ({}));
      setError({
        text: data.detail || "Não foi possível criar a conta",
        taken: res.status === 409,
      });
    } catch {
      setError({ text: "Não foi possível criar a conta. Verifique a conexão", taken: false });
    }
    setSaving(false);
  }

  return (
    <form onSubmit={onSubmit}>
      <div className="space-y-4">
        <Field label="Nome" htmlFor="name">
          <Input
            id="name"
            autoComplete="name"
            maxLength={120}
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        <Field label="E-mail" htmlFor="email">
          <Input
            id="email"
            type="email"
            autoComplete="username"
            maxLength={255}
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <NewPasswordFields
          password={password}
          confirm={confirm}
          onPassword={setPassword}
          onConfirm={setConfirm}
        />
      </div>

      {error && (
        <p role="alert" className="mt-3 text-[13px] text-negative">
          {error.text}
          {error.taken && (
            <>
              {" "}
              <Link href="/login" className="underline">
                Entrar
              </Link>
            </>
          )}
        </p>
      )}

      <Button type="submit" variant="primary" disabled={!ready || saving} className="mt-5 w-full">
        {saving ? "Criando conta" : "Criar conta"}
      </Button>
    </form>
  );
}

export default function CadastroPage() {
  const { state, reload, expire } = useInvite("signup");
  // undefined = ainda conferindo a sessão; null = ninguém logado.
  const [current, setCurrent] = useState<User | null | undefined>(undefined);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    fetch("/api/auth/me", { cache: "no-store" })
      .then(async (r) => setCurrent(r.ok ? await r.json() : null))
      .catch(() => setCurrent(null));
  }, []);

  async function logout() {
    setLeaving(true);
    const ok = await fetch("/api/auth/logout", { method: "POST" })
      .then((r) => r.ok)
      .catch(() => false);
    if (ok) setCurrent(null);
    setLeaving(false);
  }

  return (
    <AuthCard title="Criar sua conta" subtitle="Você foi convidado para o Octus Chat">
      {current === undefined ? (
        <div className="flex justify-center py-6">
          <Spinner />
        </div>
      ) : current ? (
        <>
          <p className="text-[13px] leading-5 text-fg-2">
            Você já está conectado como <span className="text-fg">{current.name}</span> (
            {current.email})
          </p>
          <div className="mt-5 space-y-2">
            <Button variant="primary" href="/" className="w-full">
              Ir para o painel
            </Button>
            <Button variant="secondary" onClick={logout} disabled={leaving} className="w-full">
              Sair e usar o convite
            </Button>
          </div>
        </>
      ) : (
        <>
          <InviteGate state={state} onRetry={reload}>
            {({ token, invite }) => (
              <SignupForm token={token} invite={invite} onGone={expire} />
            )}
          </InviteGate>
          <p className="mt-4 text-[13px] text-fg-3">
            Já tem conta?{" "}
            <Link href="/login" className="text-fg-2 underline hover:text-fg">
              Entrar
            </Link>
          </p>
        </>
      )}
    </AuthCard>
  );
}
