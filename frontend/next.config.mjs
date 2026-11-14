/** @type {import('next').NextConfig} */

// As chamadas ao backend passam pelo route handler `app/api/backend/[...path]`,
// que confere a sessão e injeta o segredo da API server-side (não usamos
// `rewrites`, que não conseguem adicionar o segredo).
const nextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
