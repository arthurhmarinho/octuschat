"use client";

import { useCallback, useEffect, useState } from "react";

export type InviteInfo = {
  valid: boolean;
  purpose: "signup" | "reset" | null;
  name: string | null;
  email: string | null;
  ig_username: string | null;
};

export type InviteState =
  | { status: "loading" }
  | { status: "invalid" }
  | { status: "error" }
  | { status: "ok"; token: string; invite: InviteInfo };

/** Lê o `?c=` da URL e confere o link. Um link do outro tipo conta como inválido. */
export function useInvite(purpose: "signup" | "reset") {
  const [state, setState] = useState<InviteState>({ status: "loading" });

  const load = useCallback(async () => {
    setState({ status: "loading" });
    const token = new URLSearchParams(window.location.search).get("c") ?? "";
    try {
      const res = await fetch(`/api/auth/invite?c=${encodeURIComponent(token)}`, {
        cache: "no-store",
      });
      if (!res.ok) return setState({ status: "error" });
      const invite = (await res.json()) as InviteInfo;
      setState(
        invite.valid && invite.purpose === purpose
          ? { status: "ok", token, invite }
          : { status: "invalid" },
      );
    } catch {
      setState({ status: "error" });
    }
  }, [purpose]);

  useEffect(() => {
    load();
  }, [load]);

  /** O envio voltou 410: o link deixou de valer enquanto a pessoa preenchia. */
  const expire = useCallback(() => setState({ status: "invalid" }), []);

  return { state, reload: load, expire };
}
