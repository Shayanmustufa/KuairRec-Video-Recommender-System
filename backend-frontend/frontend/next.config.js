/** @type {import('next').NextConfig} */

// Next.js compiles rewrites at build time, so API_INTERNAL_URL must be set when
// `next build` runs (the Dockerfile passes it as a build argument). It is the
// API origin only, e.g. http://backend:8080 — never include a path.
const apiOrigin = (process.env.API_INTERNAL_URL || 'http://127.0.0.1:8080').replace(/\/+$/, '');

const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${apiOrigin}/api/:path*` },
      { source: '/healthz', destination: `${apiOrigin}/healthz` },
      { source: '/readyz', destination: `${apiOrigin}/readyz` },
      { source: '/metrics-api', destination: `${apiOrigin}/metrics` },
    ];
  },
};

module.exports = nextConfig;
