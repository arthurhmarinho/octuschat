"use client";

import { useState, type FormEvent } from "react";
import { Button, Card, Field, Input } from "@/components/ui";

/** Só aceita caminhos internos no `?next=` (evita open redirect). */
function safeNext(): string {
  const next = new URLSearchParams(window.location.search).get("next") || "/";
  return next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        // Convite novo: a senha é temporária e precisa ser trocada antes de tudo.
        window.location.replace(data.must_change_password ? "/primeiro-acesso" : safeNext());
        return;
      }
      const data = await res.json().catch(() => ({}));
      setError(data.detail || "E-mail ou senha incorretos");
    } catch {
      setError("Não foi possível entrar. Verifique a conexão");
    }
    setLoading(false);
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-4">
      <Card padding="none" className="w-full max-w-[360px] rounded-panel p-6">
        <form onSubmit={onSubmit}>
          <h1 className="text-base font-medium text-fg">Octus Chat</h1>
          <p className="mb-6 mt-1 text-[13px] text-fg-2">Entre na sua conta</p>

          <div className="space-y-4">
          <Field label="E-mail" htmlFor="email">
            <Input
              id="email"
              type="email"
              autoComplete="username"
              autoFocus
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>

          <Field label="Senha" htmlFor="password">
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          </div>

          {error && (
            <p role="alert" className="mt-3 text-[13px] text-negative">
              {error}
            </p>
          )}

          <Button
            type="submit"
            variant="primary"
            disabled={loading || !email || !password}
            className="mt-5 w-full"
          >
            {loading ? "Entrando" : "Entrar"}
          </Button>

          <p className="mt-4 text-[13px] text-fg-3">
            Não tem acesso? Peça um convite a quem administra o painel
          </p>
        </form>
      </Card>
    </main>
  );
}
