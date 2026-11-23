"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Bot,
  Check,
  ChevronsUpDown,
  House,
  LogOut,
  Megaphone,
  Menu,
  MessagesSquare,
  Plus,
  Users,
  Workflow,
  X,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import Avatar from "@/components/Avatar";
import { Button, IconButton, StatusDot, cx } from "@/components/ui";
import { useAccount, type Account } from "@/lib/account";
import { useUser } from "@/lib/user";

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

const accountName = (a: Account) => (a.username ? `@${a.username}` : a.ig_user_id);

/** Conta do Instagram atual. Com mais de uma, abre um menu para trocar. */
function AccountSwitcher({ active }: { active: boolean }) {
  const { account, accounts, setAccountId } = useAccount();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const row = cx(
    "flex h-10 w-full items-center gap-2 rounded-control px-2 text-[13px]",
    "transition-[background-color,color] duration-150 ease-out"
  );

  if (!account) {
    return (
      <Link
        href="/configuracoes"
        className={cx(row, active ? "bg-raised text-fg" : "text-fg-2 hover:bg-raised/60")}
      >
        Conectar conta
      </Link>
    );
  }

  const dot = <StatusDot tone={account.needs_reconnect ? "negative" : "positive"} />;
  const label = (
    <>
      <Avatar name={accountName(account)} size={24} />
      <span className="min-w-0 flex-1 truncate text-left">{accountName(account)}</span>
      <span title={account.needs_reconnect ? "Reconecte o Instagram" : "Conectada"}>{dot}</span>
    </>
  );

  // Uma conta só: o bloco leva às Configurações, sem menu.
  if (accounts.length < 2) {
    return (
      <Link
        href="/configuracoes"
        aria-label={
          account.needs_reconnect
            ? `${accountName(account)}: reconecte o Instagram`
            : `${accountName(account)}, abrir configurações`
        }
        className={cx(row, active ? "bg-raised text-fg" : "text-fg-2 hover:bg-raised/60")}
      >
        {label}
      </Link>
    );
  }

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={cx(row, "text-fg-2 hover:bg-raised/60")}
      >
        {label}
        <ChevronsUpDown size={14} strokeWidth={1.5} className="shrink-0 text-fg-3" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute bottom-full left-0 right-0 z-10 mb-1 rounded-card border border-line-strong bg-raised p-1 shadow-[0_8px_24px_rgba(0,0,0,0.4)]"
        >
          {accounts.map((a) => (
            <button
              key={a.ig_user_id}
              role="menuitemradio"
              aria-checked={a.ig_user_id === account.ig_user_id}
              type="button"
              onClick={() => {
                setAccountId(a.ig_user_id);
                setOpen(false);
              }}
              className="flex h-8 w-full items-center gap-2 rounded-control px-2 text-[13px] text-fg-2 transition-colors duration-150 hover:bg-card hover:text-fg"
            >
              <span className="min-w-0 flex-1 truncate text-left">{accountName(a)}</span>
              {a.needs_reconnect && <StatusDot tone="negative" />}
              {a.ig_user_id === account.ig_user_id && (
                <Check size={14} strokeWidth={1.5} className="shrink-0 text-fg" />
              )}
            </button>
          ))}
          <div className="my-1 border-t border-line" />
          <a
            role="menuitem"
            href="/api/backend/instagram/connect"
            className="flex h-8 items-center gap-2 rounded-control px-2 text-[13px] text-fg-2 transition-colors duration-150 hover:bg-card hover:text-fg"
          >
            <Plus size={14} strokeWidth={1.5} className="shrink-0 text-fg-3" />
            Conectar outra conta
          </a>
        </div>
      )}
    </div>
  );
}

function Sidebar({ pathname }: { pathname: string }) {
  const { user } = useUser();
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    window.location.replace("/login");
  }

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
        {user && (
          <div className="px-2 pb-2">
            <p className="truncate text-[13px] font-medium text-fg">{user.name}</p>
            <p className="truncate text-xs text-fg-3">{user.email}</p>
          </div>
        )}
        <AccountSwitcher active={isActive("/configuracoes")} />
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
  const router = useRouter();
  const { user } = useUser();
  const [open, setOpen] = useState(false);

  // Senha temporária: nada funciona antes de trocá-la.
  useEffect(() => {
    if (user?.must_change_password) router.replace("/primeiro-acesso");
  }, [user, router]);

  // Fecha o drawer ao navegar.
  useEffect(() => setOpen(false), [pathname]);

  return (
    <div className={cx("flex", fill ? "h-screen" : "min-h-screen")}>
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

        <div
          className={cx(
            "mx-auto w-full max-w-[1440px] flex-1 px-4 py-8 md:px-8",
            fill && "flex min-h-0 flex-col"
          )}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
