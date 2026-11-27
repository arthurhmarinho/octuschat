"use client";

import { useCallback, useEffect, useState } from "react";
import type { Account } from "@/lib/account";

export type Onboarding = {
  /** @ do convite; null para quem não entrou por convite. */
  invited_ig_username: string | null;
  meta_tester_added: boolean;
  accounts: Account[];
};

/** Estado real da configuração. Relê quando a pessoa volta para a aba. */
export function useOnboarding() {
  const [data, setData] = useState<Onboarding | null>(null);
  const [failed, setFailed] = useState(false);

  const reload = useCallback(async () => {
    try {
      const r = await fetch("/api/backend/auth/onboarding", { cache: "no-store" });
      if (!r.ok) throw new Error(String(r.status));
      setData(await r.json());
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    reload();
    const onVisible = () => document.visibilityState === "visible" && reload();
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [reload]);

  return { data, failed, reload };
}

/** Passos que a API não sabe responder: ficam marcados neste navegador. */
export type Checks = { professional: boolean; messages: boolean };

const NONE: Checks = { professional: false, messages: false };
const key = (uid: number) => `octus.onboarding.${uid}`;

export function useChecks(uid: number | undefined) {
  const [checks, setChecks] = useState<Checks>(NONE);

  useEffect(() => {
    if (uid === undefined) return;
    try {
      const saved = JSON.parse(window.localStorage.getItem(key(uid)) ?? "{}");
      setChecks({ professional: !!saved?.professional, messages: !!saved?.messages });
    } catch {
      setChecks(NONE);
    }
  }, [uid]);

  function toggle(name: keyof Checks, value: boolean) {
    const next = { ...checks, [name]: value };
    setChecks(next);
    if (uid === undefined) return;
    try {
      window.localStorage.setItem(key(uid), JSON.stringify(next));
    } catch {
      /* modo privado: vale só nesta visita */
    }
  }

  return { checks, toggle };
}
