import { NextResponse } from "next/server";
import { failDelay, setSessionCookie } from "@/lib/authServer";
import { SECRET_HEADER, backendBase } from "@/lib/backend";

export const runtime = "nodejs";

const BAD_LOGIN = "E-mail ou senha incorretos";

/**
 * Login por e-mail e senha. Quem valida é o backend (`POST /auth/login`); aqui
 * só gravamos o cookie de sessão com o id do usuário devolvido.
 */
export async function POST(req: Request) {
  const sessionSecret = process.env.SESSION_SECRET;
  const apiSecret = process.env.BACKEND_API_SECRET;
  if (!sessionSecret || !apiSecret) {
    return NextResponse.json(
      { detail: "Login não configurado (SESSION_SECRET / BACKEND_API_SECRET)." },
      { status: 500 },
    );
  }

  let email = "";
  let password = "";
  try {
    const body = await req.json();
    email = typeof body?.email === "string" ? body.email.trim() : "";
    password = typeof body?.password === "string" ? body.password : "";
  } catch {
    /* corpo inválido = credencial vazia */
  }

  const fail = async () => {
    await failDelay();
    return NextResponse.json({ detail: BAD_LOGIN }, { status: 401 });
  };
  if (!email || !password) return fail();

  let upstream: Response;
  try {
    upstream = await fetch(`${backendBase()}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json", [SECRET_HEADER]: apiSecret },
      body: JSON.stringify({ email, password }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { detail: "Não foi possível entrar. Verifique a conexão" },
      { status: 502 },
    );
  }
  if (upstream.status === 401) return fail();
  if (!upstream.ok) {
    return NextResponse.json(
      { detail: "Não foi possível entrar. Tente de novo em instantes" },
      { status: 502 },
    );
  }

  const user = (await upstream.json()) as { id: number; must_change_password: boolean };
  const res = NextResponse.json({ ok: true, must_change_password: user.must_change_password });
  await setSessionCookie(res, sessionSecret, user.id);
  return res;
}
