/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: process.env.API_INTERNAL_URL || "http://127.0.0.1:8080/api/:path*",
      },
      {
        source: "/healthz",
        destination: process.env.API_INTERNAL_URL ? `${process.env.API_INTERNAL_URL.replace(/\/api\/?$/, '')}/healthz` : "http://127.0.0.1:8080/healthz",
      },
      {
        source: "/readyz",
        destination: process.env.API_INTERNAL_URL ? `${process.env.API_INTERNAL_URL.replace(/\/api\/?$/, '')}/readyz` : "http://127.0.0.1:8080/readyz",
      },
      {
        source: "/metrics-api",
        destination: process.env.API_INTERNAL_URL ? `${process.env.API_INTERNAL_URL.replace(/\/api\/?$/, '')}/metrics` : "http://127.0.0.1:8080/metrics",
      },
    ];
  },
};

module.exports = nextConfig;
