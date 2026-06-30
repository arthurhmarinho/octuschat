"use client";

import { useEffect, useState } from "react";

export type Account = {
  ig_user_id: string;
  username: string | null;
  connected_at: string;
};

/** Busca as contas conectadas, preferindo uma real (não "demo"). */
export async function fetchAccounts(): Promise<Account[]> {
  try {
    const r = await fetch("/api/backend/instagram/accounts");
    if (!r.ok) return [];
    return await r.json();
  } catch {
    return [];
  }
}

function pickCurrent(accounts: Account[]): Account | null {
  if (!accounts.length) return null;
  return accounts.find((a) => a.ig_user_id !== "demo") ?? accounts[0];
}

/** Hook: resolve a conta conectada atual (id + username). */
export function useAccount() {
  const [account, setAccount] = useState<Account | null>(null);
  const [resolved, setResolved] = useState(false);

  useEffect(() => {
    fetchAccounts().then((accts) => {
      setAccount(pickCurrent(accts));
      setResolved(true);
    });
  }, []);

  return { account, accountId: account?.ig_user_id ?? null, resolved };
}
