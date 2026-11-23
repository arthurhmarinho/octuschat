"use client";

import { useEffect, useSyncExternalStore } from "react";

export type User = {
  id: number;
  email: string;
  name: string;
  is_admin: boolean;
  must_change_password: boolean;
};

type State = { user: User | null; resolved: boolean };

const SERVER_STATE: State = { user: null, resolved: false };
let state: State = SERVER_STATE;
const listeners = new Set<() => void>();
let loading: Promise<void> | null = null;

function set(next: State) {
  state = next;
  listeners.forEach((l) => l());
}

/** Busca o usuário logado (`/api/auth/me`). */
export async function refreshUser(): Promise<void> {
  let user: User | null = null;
  try {
    const r = await fetch("/api/auth/me", { cache: "no-store" });
    if (r.ok) user = await r.json();
  } catch {
    /* sem rede: a tela segue sem o bloco do usuário */
  }
  set({ user, resolved: true });
}

/** Atualiza o usuário em memória (ex.: depois de trocar a senha). */
export function setUser(user: User): void {
  set({ user, resolved: true });
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useUser() {
  const snap = useSyncExternalStore(subscribe, () => state, () => SERVER_STATE);
  useEffect(() => {
    if (!loading) loading = refreshUser();
  }, []);
  return { user: snap.user, resolved: snap.resolved };
}
