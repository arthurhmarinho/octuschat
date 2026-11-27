"use client";

import { useEffect, useState } from "react";
import { Note } from "@/components/ui";

const FAILURE = "Não foi possível conectar a conta do Instagram. Tente de novo";

/** Um texto para cada `reason` que o callback do backend manda. */
const REASONS: Record<string, string> = {
  denied:
    "A conexão foi cancelada na tela do Instagram. Para continuar, tente de novo e permita o acesso",
  exchange: "A Meta não concluiu a conexão. Tente de novo em instantes",
  owned: "Essa conta do Instagram já está ligada a outro usuário",
  state: "O link de conexão expirou, tente de novo",
};

/** Resultado do callback do OAuth (`?connected=ok|error` e `&reason=`). */
export default function ConnectNotice() {
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const result = q.get("connected");
    if (result === "ok") setNotice({ ok: true, text: "Conta do Instagram conectada" });
    else if (result === "error") {
      setNotice({ ok: false, text: REASONS[q.get("reason") ?? ""] ?? FAILURE });
    }
  }, []);

  if (!notice) return null;
  return (
    <Note variant={notice.ok ? "info" : "warning"} className="mb-4">
      {notice.text}
    </Note>
  );
}
