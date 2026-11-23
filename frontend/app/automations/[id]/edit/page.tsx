"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { Card, Note, Skeleton } from "@/components/ui";
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
          excludeKeywords: a.exclude_keywords ?? "",
          postId: a.post_id ?? "",
          scope: a.post_id ? "specific" : a.bind_next ? "next" : "all",
          publicReply: a.public_reply ?? "",
          graph: a.graph ?? null,
        });
      })
      .catch(() => setError(true));
  }, [id]);

  if (error) {
    return (
      <AppShell title="Editar automação">
        <Note variant="warning">
          Não foi possível carregar esta automação. Verifique a conexão e tente de novo
        </Note>
      </AppShell>
    );
  }

  if (!initial) {
    return (
      <AppShell title="Editar automação">
        <div aria-busy="true" aria-label="Carregando" className="grid gap-8 lg:grid-cols-[1fr_320px]">
          <div className="space-y-8">
            <Skeleton className="h-5 w-32" />
            <Card className="space-y-5">
              {[0, 1, 2].map((i) => (
                <div key={i} className="space-y-2">
                  <Skeleton className="h-3.5 w-20" />
                  <Skeleton className="h-9 w-full" />
                </div>
              ))}
            </Card>
          </div>
          <Skeleton className="hidden h-[420px] rounded-panel lg:block" />
        </div>
      </AppShell>
    );
  }

  return <AutomationForm automationId={id} initial={initial} />;
}
