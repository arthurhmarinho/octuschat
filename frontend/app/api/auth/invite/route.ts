import { NextResponse, type NextRequest } from "next/server";
import { failDelay } from "@/lib/authServer";
import { SECRET_HEADER, backendBase } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Consulta um link de convite (`?c=<token>`) antes de mostrar o formulário. */
export async function GET(req: NextRequest) {
  const secret = process.env.BACKEND_API_SECRET;
  if (!secret) {
    return NextResponse.json({ detail: "BACKEND_API_SECRET não configurado." }, { status: 500 });
  }

  const invalid = async () => {
    await failDelay();
    return NextResponse.json({ valid: false });
  };
  const token = req.nextUrl.searchParams.get("c") ?? "";
  // Só o alfabeto do token: nada que mude o caminho no backend.
  if (!/^[A-Za-z0-9_-]{1,200}$/.test(token)) return invalid();

  try {
    const upstream = await fetch(`${backendBase()}/auth/invites/${token}`, {
      headers: { [SECRET_HEADER]: secret },
      cache: "no-store",
    });
    if (upstream.ok) {
      const data = await upstream.json();
      return data.valid ? NextResponse.json(data) : invalid();
    }
  } catch {
    /* cai no erro abaixo */
  }
  await failDelay();
  return NextResponse.json({ detail: "Backend indisponível" }, { status: 502 });
}
