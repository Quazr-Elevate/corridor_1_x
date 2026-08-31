/** @type {import('next').NextConfig} */

// Where /api/* calls get proxied. In prod (Railway) set API_PROXY_TARGET to
// the backend service URL; locally it falls back to the uvicorn default.
// Proxying through the frontend's own origin keeps the backend's cookies
// first-party (SameSite=lax works), so the OTP → signup cookie bridge holds.
const API_PROXY_TARGET = process.env.API_PROXY_TARGET || "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_PROXY_TARGET}/:path*`,
      },
    ];
  },
};

export default nextConfig;
