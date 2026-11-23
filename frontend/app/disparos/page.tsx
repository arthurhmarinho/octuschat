"use client";

import { useEffect, useState } from "react";
import { Send } from "lucide-react";
import AppShell from "@/components/AppShell";
import { Button, Card, Field, Note, Textarea } from "@/components/ui";
import { useAccount } from "@/lib/account";

export default function DisparosPage() {
  const { accountId, resolved } = useAccount();
  const [count, setCount] = useState<number | null>(null);
  const [text, setText] = useState("");

  useEffect(() => {
    if (!resolved) return;
    if (!accountId) {
      setCount(0);
      return;
    }
    fetch(`/api/backend/contacts?account_id=${accountId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: unknown[]) => setCount(data.length))
      .catch(() => setCount(0));
  }, [accountId, resolved]);

  return (
    <AppShell title="Disparos">
      <div className="max-w-2xl space-y-4">
        <p className="text-sm text-fg-2">Envie uma mensagem para vários contatos de uma vez</p>

        <Card className="space-y-4">
          <Field label="Mensagem" htmlFor="broadcast">
            <Textarea
              id="broadcast"
              rows={5}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Escreva o disparo"
            />
          </Field>

          <div className="flex items-center justify-between gap-4">
            <span className="font-mono text-xs text-fg-3">
              {count === null ? "—" : count} {count === 1 ? "contato" : "contatos"}
            </span>
            <div className="flex items-center gap-3">
              <span className="text-xs text-fg-3">Envio em massa ainda não está disponível</span>
              <Button variant="primary" icon={Send} disabled>
                Disparar
              </Button>
            </div>
          </div>
        </Card>

        <Note>Só recebem quem mandou mensagem nas últimas 24 horas</Note>
      </div>
    </AppShell>
  );
}
