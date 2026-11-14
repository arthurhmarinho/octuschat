/**
 * Proxy autenticado para o backend FastAPI.
 *
 * Substitui o antigo `rewrite`: confere a sessão do usuário e injeta o
 * segredo da API (BACKEND_API_SECRET) server-side — ele nunca chega ao browser.
 */

import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, verifySessionToken } from "@/lib/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Normaliza a URL do backend: remove espaços/quebras, tira "/" no fim e
// garante o esquema https:// (evita erro se a env vier sem ele).
function backendBase(): string {
  let url = (process.env.BACKEND_URL || "http://localhost:8000").trim();
  url = url.replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(url)) url = `https://${url}`;
  return url;
}

// Headers da request repassados ao backend.
const FORWARD_REQ = ["content-type", "accept"];
// Headers da resposta repassados ao browser (content-encoding/length ficam de
// fora: o fetch já descomprimiu o corpo).
const FORWARD_RES = ["content-type", "location", "cache-control"];

async function proxy(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const session = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!(await verifySessionToken(session, process.env.SESSION_SECRET))) {
    return NextResponse.json({ detail: "Não autenticado" }, { status: 401 });
  }

  const secret = process.env.BACKEND_API_SECRET;
  if (!secret) {
    return NextResponse.json(
      { detail: "BACKEND_API_SECRET não configurado no frontend." },
      { status: 500 },
    );
  }

  const { path } = await params;
  const target = `${backendBase()}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;

  const headers = new Headers({ "X-Octus-Secret": secret });
  for (const h of FORWARD_REQ) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }

  const hasBody = !["GET", "HEAD"].includes(req.method);
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      // Redirects (ex.: /instagram/connect → tela da Meta) vão para o browser.
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "Backend indisponível" }, { status: 502 });
  }

  const resHeaders = new Headers();
  for (const h of FORWARD_RES) {
    const v = upstream.headers.get(h);
    if (v) resHeaders.set(h, v);
  }
  const noBody = upstream.status === 204 || upstream.status === 304;
  return new NextResponse(noBody ? null : upstream.body, {
    status: upstream.status,
    headers: resHeaders,
  });
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
};
