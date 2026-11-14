import { createHash, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { SESSION_COOKIE, SESSION_MAX_AGE, createSessionToken } from "@/lib/session";

export const runtime = "nodejs";

function sameSecret(a: string, b: string): boolean {
  // Hash antes de comparar: timingSafeEqual exige tamanhos iguais.
  const ha = createHash("sha256").update(a).digest();
  const hb = createHash("sha256").update(b).digest();
  return timingSafeEqual(ha, hb);
}

export async function POST(req: Request) {
  const adminPassword = process.env.ADMIN_PASSWORD;
  const sessionSecret = process.env.SESSION_SECRET;
  if (!adminPassword || !sessionSecret) {
    return NextResponse.json(
      { detail: "Login não configurado (ADMIN_PASSWORD / SESSION_SECRET)." },
      { status: 500 },
    );
  }

  let password = "";
  try {
    const body = await req.json();
    password = typeof body?.password === "string" ? body.password : "";
  } catch {
    /* corpo inválido = senha vazia */
  }

  if (!password || !sameSecret(password, adminPassword)) {
    // Atraso fixo: freia tentativa de força bruta sem precisar de estado.
    await new Promise((r) => setTimeout(r, 1000));
    return NextResponse.json({ detail: "Senha incorreta" }, { status: 401 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, await createSessionToken(sessionSecret), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_MAX_AGE,
  });
  return res;
}
