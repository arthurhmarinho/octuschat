"use client";

import { useEffect, useState } from "react";
import { Note } from "@/components/ui";

type Status = "ok" | "error" | "owned";

/** Resultado do callback do OAuth (`?connected=ok|error`, e `&reason=owned`). */
export default function ConnectNotice() {
  const [status, setStatus] = useState<Status | null>(null);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const v = q.get("connected");
    if (v === "ok") setStatus("ok");
    else if (v === "error") setStatus(q.get("reason") === "owned" ? "owned" : "error");
  }, []);

  if (!status) return null;
  return (
    <Note variant={status === "ok" ? "info" : "warning"} className="mb-4">
      {status === "ok"
        ? "Conta do Instagram conectada"
        : status === "owned"
          ? "Essa conta do Instagram já está ligada a outro usuário"
          : "Não foi possível conectar a conta do Instagram. Tente de novo"}
    </Note>
  );
}
