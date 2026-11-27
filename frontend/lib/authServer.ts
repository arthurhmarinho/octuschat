/**
 * Pedaços comuns dos route handlers de `/api/auth/*` (só servidor): cookie de
 * sessão, atraso nas falhas e o envio de cadastro/redefinição ao backend.
 */

import { NextResponse } from "next/server";
import { SECRET_HEADER, backendBase } from "@/lib/backend";
import { SESSION_COOKIE, SESSION_MAX_AGE, createSessionToken } from "@/lib/session";

/** Atraso fixo nas falhas: freia força bruta sem precisar de estado. */
export const failDelay = () => new Promise((r) => setTimeout(r, 1000));

export async function setSessionCookie(res: NextResponse, sessionSecret: string, uid: number) {
  res.cookies.set(SESSION_COOKIE, await createSessionToken(sessionSecret, uid), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_MAX_AGE,
  });
}

/** Recusas do backend cujo `detail` a tela pode mostrar. */
const SHOWN = [409, 410, 422];

/**
 * Repassa o formulário de um link (cadastro ou redefinição) ao backend e, se
 * der certo, já entra: grava o cookie com o usuário devolvido. Só os campos
 * listados em `fields` são repassados.
 */
export async function submitInvite(req: Request, path: string, fields: readonly string[]) {
  const sessionSecret = process.env.SESSION_SECRET;
  const apiSecret = process.env.BACKEND_API_SECRET;
  if (!sessionSecret || !apiSecret) {
    return NextResponse.json(
      { detail: "Login não configurado (SESSION_SECRET / BACKEND_API_SECRET)." },
      { status: 500 },
    );
  }

  let input: Record<string, unknown> = {};
  try {
    input = (await req.json()) ?? {};
  } catch {
    /* corpo inválido = campos vazios; o backend recusa */
  }
  const body = Object.fromEntries(
    fields.map((f) => [f, typeof input[f] === "string" ? input[f] : ""]),
  );

  const unavailable = () =>
    NextResponse.json(
      { detail: "Não foi possível concluir. Tente de novo em instantes" },
      { status: 502 },
    );

  let upstream: Response;
  try {
    upstream = await fetch(`${backendBase()}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", [SECRET_HEADER]: apiSecret },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    return unavailable();
  }

  if (!upstream.ok) {
    if (!SHOWN.includes(upstream.status)) return unavailable();
    await failDelay();
    const data = await upstream.json().catch(() => ({}));
    const detail = typeof data.detail === "string" ? data.detail : "Confira os dados e tente de novo";
    return NextResponse.json({ detail }, { status: upstream.status });
  }

  const user = (await upstream.json()) as { id: number };
  const res = NextResponse.json({ ok: true });
  await setSessionCookie(res, sessionSecret, user.id);
  return res;
}
