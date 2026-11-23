/** URL do backend FastAPI (server-side). Normaliza espaços, "/" final e esquema. */
export function backendBase(): string {
  let url = (process.env.BACKEND_URL || "http://localhost:8000").trim();
  url = url.replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(url)) url = `https://${url}`;
  return url;
}

/** Header com o segredo compartilhado com o backend. */
export const SECRET_HEADER = "X-Octus-Secret";
/** Header com o id do usuário da sessão (só o servidor do Next o define). */
export const USER_HEADER = "X-Octus-User";
