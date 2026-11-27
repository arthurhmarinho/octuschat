import { submitInvite } from "@/lib/authServer";

export const runtime = "nodejs";

/** Cadastro por convite: cria a conta no backend e já grava a sessão. */
export async function POST(req: Request) {
  return submitInvite(req, "/auth/register", ["token", "name", "email", "password"]);
}
