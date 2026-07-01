"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import AppShell from "@/components/AppShell";
import AutomationForm, { type AutomationInitial } from "@/components/AutomationForm";

export default function EditAutomationPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [initial, setInitial] = useState<AutomationInitial | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch(`/api/backend/automations/${id}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((a) => {
        setInitial({
          name: a.name ?? "",
          trigger: a.trigger,
          keyword: a.keyword ?? "",
          postId: a.post_id ?? "",
          scope: a.post_id ? "specific" : "all",
          replyMessage: a.reply_message ?? "",
          linkUrl: a.link_url ?? "",
          linkLabel: a.link_label ?? "",
        });
      })
      .catch(() => setError(true));
  }, [id]);

  if (error) {
    return (
      <AppShell title="Editar automação">
        <div className="glass p-6 text-sm text-amber-400">
          Não foi possível carregar esta automação.
        </div>
      </AppShell>
    );
  }

  if (!initial) {
    return (
      <AppShell title="Editar automação">
        <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
          <Loader2 size={16} className="animate-spin" /> Carregando…
        </div>
      </AppShell>
    );
  }

  return <AutomationForm automationId={id} initial={initial} />;
}
