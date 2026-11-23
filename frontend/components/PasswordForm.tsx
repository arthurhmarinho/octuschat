"use client";

import { useState, type FormEvent } from "react";
import { Button, Field, Input } from "@/components/ui";
import { setUser, type User } from "@/lib/user";

export const MIN_PASSWORD = 10;

/**
 * Troca de senha (Configurações e primeiro acesso). A validação de tamanho
 * espelha o backend, que é quem manda; aqui só poupa uma ida ao servidor.
 */
export default function PasswordForm({
  onDone,
  submitLabel = "Alterar senha",
}: {
  onDone?: (user: User) => void;
  submitLabel?: string;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);

  const tooShort = next.length > 0 && next.length < MIN_PASSWORD;
  const mismatch = confirm.length > 0 && confirm !== next;
  const ready = !!current && next.length >= MIN_PASSWORD && confirm === next;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!ready) return;
    setSaving(true);
    setError(null);
    setDone(false);
    try {
      const res = await fetch("/api/backend/auth/password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      if (res.ok) {
        const user = (await res.json()) as User;
        setUser(user);
        setCurrent("");
        setNext("");
        setConfirm("");
        setDone(true);
        onDone?.(user);
      } else {
        const data = await res.json().catch(() => ({}));
        setError(typeof data.detail === "string" ? data.detail : "Não foi possível alterar a senha");
      }
    } catch {
      setError("Não foi possível alterar a senha. Verifique a conexão");
    }
    setSaving(false);
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <Field label="Senha atual" htmlFor="pw-current">
        <Input
          id="pw-current"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
      </Field>
      <Field
        label="Nova senha"
        htmlFor="pw-new"
        hint={`Pelo menos ${MIN_PASSWORD} caracteres`}
        error={tooShort ? `Pelo menos ${MIN_PASSWORD} caracteres` : undefined}
      >
        <Input
          id="pw-new"
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
        />
      </Field>
      <Field
        label="Confirmar nova senha"
        htmlFor="pw-confirm"
        error={mismatch ? "As senhas não são iguais" : undefined}
      >
        <Input
          id="pw-confirm"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
      </Field>

      {error && (
        <p role="alert" className="text-[13px] text-negative">
          {error}
        </p>
      )}
      {done && (
        <p role="status" className="text-[13px] text-fg-2">
          Senha alterada
        </p>
      )}

      <Button type="submit" variant="primary" disabled={!ready || saving}>
        {saving ? "Salvando" : submitLabel}
      </Button>
    </form>
  );
}
