"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MessageCircle, Zap, Reply, ArrowRight } from "lucide-react";
import AppShell from "@/components/AppShell";

type HealthState = "checking" | "online" | "offline";

const TEMPLATES = [
  {
    icon: Zap,
    title: "Link na DM a partir de comentários",
    desc: "Envie um link sempre que alguém comentar em um post ou reel.",
    popular: true,
  },
  {
    icon: Reply,
    title: "Responder todas as DMs",
    desc: "Mande uma resposta automática quando alguém te enviar uma DM.",
    popular: false,
  },
  {
    icon: MessageCircle,
    title: "Crescer com comentários",
    desc: "Use comentários do Instagram para fazer sua conta crescer.",
    popular: false,
  },
];

export default function Home() {
  const [backend, setBackend] = useState<HealthState>("checking");

  useEffect(() => {
    fetch("/api/backend/health")
      .then((r) => setBackend(r.ok ? "online" : "offline"))
      .catch(() => setBackend("offline"));
  }, []);

  return (
    <AppShell title="Inicial">
      {/* Saudação + status enxuto */}
      <div className="mb-10">
        <h2 className="text-3xl font-extrabold tracking-tight">
          Olá! <span className="text-gold-gradient">Bem-vindo.</span>
        </h2>
        <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-[var(--muted)]">
          <span className="flex items-center gap-2">
            <span className={`dot ${backend !== "online" ? "!bg-amber-400 !shadow-none" : ""}`} />
            Backend {backend === "checking" ? "…" : backend}
          </span>
          <span>0 contas conectadas</span>
          <span>0 automações ativas</span>
        </div>
      </div>

      {/* Comece aqui */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold">Comece aqui</h3>
        <Link href="/automations" className="text-sm text-[var(--gold)] hover:underline">
          Ver automações →
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {TEMPLATES.map((t) => {
          const Icon = t.icon;
          return (
            <Link
              key={t.title}
              href="/automations/new"
              className="glass group flex flex-col p-5 transition-colors hover:border-[var(--gold)]/40"
            >
              <div className="mb-4 flex items-center justify-between">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--gold)]/10 text-[var(--gold)]">
                  <Icon size={18} />
                </span>
                {t.popular && (
                  <span className="mono rounded bg-[var(--gold)]/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--gold)]">
                    Popular
                  </span>
                )}
              </div>
              <h4 className="mb-1.5 font-semibold leading-snug">{t.title}</h4>
              <p className="flex-1 text-sm leading-relaxed text-[var(--muted)]">{t.desc}</p>
              <span className="mono mt-4 flex items-center gap-1.5 text-xs text-[var(--muted)] group-hover:text-[var(--gold)]">
                Usar modelo <ArrowRight size={13} />
              </span>
            </Link>
          );
        })}
      </div>
    </AppShell>
  );
}
