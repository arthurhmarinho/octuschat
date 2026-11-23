"use client";

import { useEffect, useState } from "react";
import { Note } from "@/components/ui";

/** Resultado do callback do OAuth (`?connected=ok|error`). */
export default function ConnectNotice() {
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    const v = new URLSearchParams(window.location.search).get("connected");
    if (v === "ok" || v === "error") setStatus(v);
  }, []);

  if (!status) return null;
  return (
    <Note variant={status === "ok" ? "info" : "warning"} className="mb-4">
      {status === "ok"
        ? "Conta do Instagram conectada"
        : "Não foi possível conectar a conta do Instagram. Tente de novo"}
    </Note>
  );
}
