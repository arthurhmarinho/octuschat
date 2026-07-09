"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  Users,
  Workflow,
  Sparkles,
  MessageCircle,
  Send,
  Settings,
  HelpCircle,
} from "lucide-react";
import type { ReactNode } from "react";

const NAV = [
  { icon: Home, label: "Inicial", href: "/" },
  { icon: Users, label: "Contatos", href: "/contatos" },
  { icon: Workflow, label: "Automações", href: "/automations" },
  { icon: Sparkles, label: "IA", href: "/ia" },
  { icon: MessageCircle, label: "Conversas", href: "/conversas" },
  { icon: Send, label: "Disparos", href: "/disparos" },
  { icon: Settings, label: "Configurações", href: "/configuracoes" },
];

export default function AppShell({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <div className="flex min-h-screen">
      {/* ── Sidebar ── */}
      <aside className="fixed left-0 top-0 flex h-screen w-16 flex-col items-center border-r border-[var(--border)] bg-[rgba(7,11,20,0.6)] py-4 backdrop-blur-xl">
        <Link
          href="/"
          title="Octus Chat"
          className="mb-6 flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-[#f8d987] to-[var(--gold-deep)] text-[#2a1e05]"
        >
          <Send size={16} />
        </Link>

        <nav className="flex flex-1 flex-col gap-1.5">
          {NAV.map(({ icon: Icon, label, href }) => {
            const active = isActive(href);
            return (
              <Link
                key={href}
                href={href}
                title={label}
                className={`relative flex h-10 w-10 items-center justify-center rounded-xl transition-colors ${
                  active
                    ? "bg-[var(--gold)]/10 text-[var(--gold)]"
                    : "text-[var(--muted)] hover:bg-white/5 hover:text-white"
                }`}
              >
                {active && (
                  <span className="absolute left-0 h-5 w-0.5 rounded-r bg-[var(--gold)]" />
                )}
                <Icon size={19} />
              </Link>
            );
          })}
        </nav>

        <button
          title="Ajuda"
          className="flex h-10 w-10 items-center justify-center rounded-xl text-[var(--muted)] hover:bg-white/5 hover:text-white"
        >
          <HelpCircle size={19} />
        </button>
      </aside>

      {/* ── Conteúdo ── */}
      <div className="ml-16 flex-1">
        <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-[var(--border)] bg-[rgba(7,11,20,0.7)] px-8 backdrop-blur-xl">
          <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
          {action}
        </header>

        <div className="px-8 py-8">{children}</div>
      </div>
    </div>
  );
}
