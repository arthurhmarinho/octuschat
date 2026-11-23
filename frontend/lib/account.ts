"use client";

import { useEffect, useSyncExternalStore } from "react";

export type Account = {
  ig_user_id: string;
  username: string | null;
  connected_at: string;
  token_expires_at: string | null;
  /** A Meta recusou o token (ou ele venceu): a conta precisa ser reconectada. */
  needs_reconnect: boolean;
};

type State = { accounts: Account[]; selectedId: string | null; resolved: boolean };

const STORAGE_KEY = "octus.account";

// Estado único do módulo: AppShell e páginas leem a mesma conta atual, então
// trocar no seletor da barra lateral recarrega os dados da página.
const SERVER_STATE: State = { accounts: [], selectedId: null, resolved: false };
let state: State = SERVER_STATE;
const listeners = new Set<() => void>();
let loading: Promise<void> | null = null;

function set(next: State) {
  state = next;
  listeners.forEach((l) => l());
}

function readSaved(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/** A salva, se ainda existir entre as contas do usuário; senão a primeira. */
export function chooseAccount(accounts: Account[], saved: string | null): string | null {
  return accounts.find((a) => a.ig_user_id === saved)?.ig_user_id ?? accounts[0]?.ig_user_id ?? null;
}

/** Busca as contas do usuário logado (a API já devolve só as dele). */
export async function refreshAccounts(): Promise<void> {
  let accounts: Account[] = [];
  try {
    const r = await fetch("/api/backend/instagram/accounts");
    if (r.ok) accounts = await r.json();
  } catch {
    /* sem contas: a tela mostra o estado de "conectar" */
  }
  set({
    accounts,
    selectedId: chooseAccount(accounts, state.selectedId ?? readSaved()),
    resolved: true,
  });
}

export function setAccountId(id: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, id);
  } catch {
    /* modo privado: vale só nesta aba */
  }
  set({ ...state, selectedId: chooseAccount(state.accounts, id) });
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Hook: contas do usuário e a conta atual (id + username). */
export function useAccount() {
  const snap = useSyncExternalStore(subscribe, () => state, () => SERVER_STATE);

  useEffect(() => {
    if (!loading) loading = refreshAccounts();
  }, []);

  const account = snap.accounts.find((a) => a.ig_user_id === snap.selectedId) ?? null;
  return {
    account,
    accountId: account?.ig_user_id ?? null,
    accounts: snap.accounts,
    setAccountId,
    refreshAccounts,
    resolved: snap.resolved,
  };
}
