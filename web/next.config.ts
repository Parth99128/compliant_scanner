import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Same-origin API proxy: the browser only ever talks to :3000 (which
  // demonstrably loads), while Node forwards /api/* to the backend. This
  // bypasses per-browser network blocks (VPN clients, DNS filters, IPv6
  // localhost quirks) that can break direct browser -> 127.0.0.1:8001 calls.
  // Used only when NEXT_PUBLIC_API_URL is unset (local dev); docker/prod
  // builds set an absolute backend URL and bypass the proxy.
  async rewrites() {
    return [{ source: "/api/:path*", destination: "http://127.0.0.1:8001/api/:path*" }];
  },
};

export default nextConfig;
