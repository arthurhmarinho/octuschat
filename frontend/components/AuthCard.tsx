import type { ReactNode } from "react";
import { Card } from "@/components/ui";

/** Cartão central das telas sem barra lateral (cadastro e redefinição). */
export default function AuthCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-4 py-8">
      <Card padding="none" className="w-full max-w-[360px] rounded-panel p-6">
        <h1 className="text-base font-medium text-fg">{title}</h1>
        {subtitle && <p className="mt-1 text-[13px] text-fg-2">{subtitle}</p>}
        <div className="mt-6">{children}</div>
      </Card>
    </main>
  );
}
