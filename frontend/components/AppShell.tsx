"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowLeft,
  Bot,
  House,
  LogOut,
  Megaphone,
  Menu,
  MessagesSquare,
  Users,
  Workflow,
  X,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import Avatar from "@/components/Avatar";
import { Button, IconButton, StatusDot, cx } from "@/components/ui";
import { useAccount } from "@/lib/account";

type NavItem = { icon: LucideIcon; label: string; href: string };

const NAV: NavItem[] = [
  { icon: House, label: "Início", href: "/" },
  { icon: Workflow, label: "Automações", href: "/automations" },
  { icon: MessagesSquare, label: "Conversas", href: "/conversas" },
  { icon: Users, label: "Contatos", href: "/contatos" },
];

const SOON: NavItem[] = [
  { icon: Megaphone, label: "Disparos", href: "/disparos" },
  { icon: Bot, label: "IA", href: "/ia" },
];

function NavLink({ item, active, muted }: { item: NavItem; active: boolean; muted?: boolean }) {
  const { icon: Icon, label, href } = item;
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cx(
        "flex h-8 items-center gap-2 rounded-control px-2 text-sm",
        "transition-[background-color,color] duration-150 ease-out",
        active
          ? "bg-raised font-medium text-fg shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]"
          : cx("hover:bg-raised/60", muted ? "text-fg-3" : "text-fg-2")
      )}
    >
      <Icon size={16} strokeWidth={1.5} className={active ? "text-fg" : "text-fg-3"} />
      {label}
    </Link>
  );
}

function Sidebar({ pathname }: { pathname: string }) {
  const { account } = useAccount();
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    window.location.replace("/login");
  }

  const username = account?.username ? `@${account.username}` : null;

  return (
    <div className="flex h-full flex-col bg-bg-deep p-3">
      <Link href="/" className="flex h-14 items-center px-2 text-base font-medium text-fg">
        Octus Chat
      </Link>

      <nav className="flex flex-1 flex-col gap-0.5" aria-label="Principal">
        {NAV.map((item) => (
          <NavLink key={item.href} item={item} active={isActive(item.href)} />
        ))}
        <p className="mb-2 mt-6 px-2 text-xs text-fg-3">Em breve</p>
        {SOON.map((item) => (
          <NavLink key={item.href} item={item} active={isActive(item.href)} muted />
        ))}
      </nav>

      <div className="flex flex-col gap-0.5 border-t border-line pt-3">
        <Link
          href="/configuracoes"
          aria-current={isActive("/configuracoes") ? "page" : undefined}
          className={cx(
            "flex h-10 items-center gap-2 rounded-control px-2 text-[13px]",
            "transition-[background-color,color] duration-150 ease-out",
            isActive("/configuracoes")
              ? "bg-raised text-fg"
              : "text-fg-2 hover:bg-raised/60"
          )}
        >
          {username ? (
            <>
              <Avatar name={username} size={24} />
              <span className="min-w-0 flex-1 truncate">{username}</span>
              <StatusDot tone="positive" />
            </>
          ) : (
            <span className="text-fg-2">Conectar conta</span>
          )}
        </Link>
        <button
          type="button"
          onClick={logout}
          className="flex h-8 items-center gap-2 rounded-control px-2 text-sm text-fg-2 transition-[background-color,color] duration-150 ease-out hover:bg-raised/60 hover:text-fg"
        >
          <LogOut size={16} strokeWidth={1.5} className="text-fg-3" />
          Sair
        </button>
      </div>
    </div>
  );
}

export default function AppShell({
  title,
  action,
  back,
  fill = false,
  children,
}: {
  title: string;
  action?: ReactNode;
  /** Link de retorno no header (ex.: builder → Automações). */
  back?: { href: string; label: string };
  /** Conteúdo ocupa toda a altura disponível (ex.: Conversas). */
  fill?: boolean;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Fecha o drawer ao navegar.
  useEffect(() => setOpen(false), [pathname]);

  return (
    <div className={cx("flex", fill ? "h-screen" : "min-h-screen")}>
      <a
        href="#conteudo"
        className="sr-only z-[70] rounded-control bg-fg px-3 py-2 text-[13px] font-medium text-on-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
      >
        Pular para o conteúdo
      </a>

      {/* Sidebar fixa (≥768) */}
      <aside className="fixed left-0 top-0 hidden h-screen w-60 border-r border-line md:block">
        <Sidebar pathname={pathname} />
      </aside>

      {/* Drawer (<768) */}
      <div
        className={cx(
          "fixed inset-0 z-50 md:hidden",
          "transition-opacity duration-200 ease-out",
          open ? "opacity-100" : "pointer-events-none opacity-0"
        )}
        aria-hidden={!open}
        // Fechado, o menu não pode receber foco por Tab.
        inert={!open}
      >
        <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
        <aside className="absolute left-0 top-0 h-full w-60 border-r border-line">
          <Sidebar pathname={pathname} />
          <IconButton
            icon={X}
            aria-label="Fechar menu"
            onClick={() => setOpen(false)}
            className="absolute right-2 top-3"
          />
        </aside>
      </div>

      {/* Conteúdo */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col md:ml-60">
        <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-line bg-bg px-4 md:px-8">
          <div className="flex items-center gap-2">
            <IconButton
              icon={Menu}
              aria-label="Abrir menu"
              onClick={() => setOpen(true)}
              className="-ml-2 md:hidden"
            />
            {back && (
              <Button variant="ghost" size="sm" icon={ArrowLeft} href={back.href} className="-ml-2">
                {back.label}
              </Button>
            )}
            <h1 className="text-base font-medium text-fg">{title}</h1>
          </div>
          {action}
        </header>

        <main
          id="conteudo"
          tabIndex={-1}
          className={cx(
            "mx-auto w-full max-w-[1440px] flex-1 px-4 py-8 outline-none md:px-8",
            fill && "flex min-h-0 flex-col"
          )}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
