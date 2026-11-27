import { submitInvite } from "@/lib/authServer";

export const runtime = "nodejs";

/** Redefinição de senha por link: troca a senha e já grava a sessão. */
export async function POST(req: Request) {
  return submitInvite(req, "/auth/reset", ["token", "password"]);
}
