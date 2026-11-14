/**
 * Sessão do admin: cookie httpOnly com `<exp>.<hmac>` assinado com
 * SESSION_SECRET. Sem estado no banco (app single-user).
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

/** Gera o valor do cookie de sessão (válido por SESSION_MAX_AGE). */
export async function createSessionToken(secret: string): Promise<string> {
  const exp = String(Math.floor(Date.now() / 1000) + SESSION_MAX_AGE);
  const sig = await crypto.subtle.sign("HMAC", await hmacKey(secret), enc.encode(exp));
  return `${exp}.${b64url(sig)}`;
}

/** Confere assinatura (tempo constante via subtle.verify) e expiração. */
export async function verifySessionToken(
  token: string | undefined,
  secret: string | undefined,
): Promise<boolean> {
  if (!token || !secret) return false;
  const [exp, sig] = token.split(".");
  if (!exp || !sig || !/^\d+$/.test(exp)) return false;
  if (Number(exp) < Math.floor(Date.now() / 1000)) return false;
  const sigBytes = fromB64url(sig);
  if (!sigBytes) return false;
  return crypto.subtle.verify("HMAC", await hmacKey(secret), sigBytes, enc.encode(exp));
}
