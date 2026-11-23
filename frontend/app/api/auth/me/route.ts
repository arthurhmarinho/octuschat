import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { SECRET_HEADER, USER_HEADER, backendBase } from "@/lib/backend";
import { SESSION_COOKIE, verifySessionToken } from "@/lib/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Quem está logado (`GET /auth/me` do backend). Fica sob /api/auth/, que o
 * middleware deixa passar, então confere a sessão aqui mesmo.
 */
export async function GET() {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  const session = await verifySessionToken(token, process.env.SESSION_SECRET);
  const secret = process.env.BACKEND_API_SECRET;
  if (!session) return NextResponse.json({ detail: "Não autenticado" }, { status: 401 });
  if (!secret) {
    return NextResponse.json({ detail: "BACKEND_API_SECRET não configurado." }, { status: 500 });
  }
  try {
    const upstream = await fetch(`${backendBase()}/auth/me`, {
      headers: { [SECRET_HEADER]: secret, [USER_HEADER]: String(session.uid) },
      cache: "no-store",
    });
    return NextResponse.json(await upstream.json().catch(() => ({})), {
      status: upstream.status,
    });
  } catch {
    return NextResponse.json({ detail: "Backend indisponível" }, { status: 502 });
  }
}
