/** @type {import('next').NextConfig} */

// Normaliza a URL do backend: remove espaços/quebras, tira "/" no fim e
// garante o esquema https:// (evita "Invalid rewrite" se a env vier sem ele).
function backendBase() {
  let url = (process.env.BACKEND_URL || "http://localhost:8000").trim();
  url = url.replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(url)) url = `https://${url}`;
  return url;
}

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backendBase()}/:path*`,
      },
    ];
  },
};

export default nextConfig;
