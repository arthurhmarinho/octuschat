/**
 * Sessão do usuário: cookie httpOnly com `<uid>.<exp>.<hmac>`, assinado com
 * SESSION_SECRET sobre `<uid>.<exp>`. Sem estado no banco: quem entrou é o uid.
 * O formato antigo (`<exp>.<hmac>`, 2 partes) é recusado: todo mundo entra de novo.
 *
 * Usa só Web Crypto, então roda tanto no middleware (edge) quanto nos
 * route handlers (node).
 */

export const SESSION_COOKIE = "octus_session";
export const SESSION_MAX_AGE = 60 * 60 * 24 * 30; // 30 dias, em segundos

const enc = new TextEncoder();

function b64url(bytes: ArrayBuffer): string {
  let s = "";
  for (const b of new Uint8Array(bytes)) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromB64url(s: string): Uint8Array<ArrayBuffer> | null {
  try {
    const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/"));
    const out = new Uint8Array(new ArrayBuffer(bin.length));
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  } catch {
    return null;
  }
}

async function hmacKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

/** Gera o valor do cookie de sessão do usuário `uid` (válido por SESSION_MAX_AGE). */
export async function createSessionToken(secret: string, uid: number): Promise<string> {
  const exp = Math.floor(Date.now() / 1000) + SESSION_MAX_AGE;
  const payload = `${uid}.${exp}`;
  const sig = await crypto.subtle.sign("HMAC", await hmacKey(secret), enc.encode(payload));
  return `${payload}.${b64url(sig)}`;
}

export type Session = { uid: number };

/**
 * Confere assinatura (tempo constante via subtle.verify) e expiração.
 * Devolve o usuário da sessão, ou null se o token for inválido, expirado
 * ou do formato antigo.
 */
export async function verifySessionToken(
  token: string | undefined,
  secret: string | undefined,
): Promise<Session | null> {
  if (!token || !secret) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const [uid, exp, sig] = parts;
  if (!/^\d{1,12}$/.test(uid) || !/^\d+$/.test(exp) || !sig) return null;
  if (Number(exp) < Math.floor(Date.now() / 1000)) return null;
  const sigBytes = fromB64url(sig);
  if (!sigBytes) return null;
  const ok = await crypto.subtle.verify(
    "HMAC",
    await hmacKey(secret),
    sigBytes,
    enc.encode(`${uid}.${exp}`),
  );
  return ok ? { uid: Number(uid) } : null;
}
