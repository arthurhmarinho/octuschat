"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { Note, Spinner } from "@/components/ui";
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
        <div className="flex justify-center py-24">
          <Spinner />
        </div>
      </AppShell>
    );
  }

  return <AutomationForm automationId={id} initial={initial} />;
}
