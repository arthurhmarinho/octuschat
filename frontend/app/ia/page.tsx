import { Bot } from "lucide-react";
import AppShell from "@/components/AppShell";
import { Card, EmptyState } from "@/components/ui";

export default function IaPage() {
  return (
    <AppShell title="IA">
      <Card padding="none">
        <EmptyState icon={Bot} title="Respostas com IA" description="Ainda não disponível" />
      </Card>
    </AppShell>
  );
}
