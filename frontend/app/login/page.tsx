"use client";

import { useState, type FormEvent } from "react";
import { Lock, Send } from "lucide-react";

/** Só aceita caminhos internos no `?next=` (evita open redirect). */
function safeNext(): string {
  const next = new URLSearchParams(window.location.search).get("next") || "/";
  return next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export default function LoginPage() {
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
        body: JSON.stringify({ password }),
      });
      if (res.ok) {
        window.location.replace(safeNext());
        return;
      }
      const data = await res.json().catch(() => ({}));
      setError(data.detail || "Não foi possível entrar.");
    } catch {
      setError("Não foi possível entrar.");
    }
    setLoading(false);
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={onSubmit} className="glass w-full max-w-sm px-6 py-8">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-[#f8d987] to-[var(--gold-deep)] text-[#2a1e05]">
            <Send size={18} />
          </span>
          <h1 className="text-lg font-semibold tracking-tight">Octus Chat</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">Entre com a senha de administrador.</p>
        </div>

        <label className="mb-1.5 block text-xs font-medium text-[var(--muted)]" htmlFor="password">
          Senha
        </label>
        <div className="relative">
          <Lock size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            autoFocus
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-[var(--border)] bg-black/30 py-2.5 pl-9 pr-3.5 text-sm outline-none transition-colors focus:border-[var(--gold)]"
          />
        </div>

        {error && <p className="mt-3 text-sm text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={loading || !password}
          className="btn-gold mt-5 w-full rounded-lg py-2.5 text-sm disabled:opacity-60"
        >
          {loading ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </main>
  );
}
