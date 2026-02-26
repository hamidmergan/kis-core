import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    // Next.js 15.x uses middlewareClientMaxBodySize for rewrite proxy body limits
    // (proxyClientMaxBodySize is only available in Next.js 16+)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ...(({ middlewareClientMaxBodySize: "500mb" }) as any),
  },
  async rewrites() {
    return [
      {
        source: "/auth/:path*",
        destination: `${backendUrl}/auth/:path*`,
      },
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
      {
        source: "/translate",
        destination: `${backendUrl}/translate`,
      },
      {
        source: "/translate-document",
        destination: `${backendUrl}/translate-document`,
      },
      {
        source: "/api/tts",
        destination: `${backendUrl}/tts`,
      },
      {
        source: "/api/voices",
        destination: `${backendUrl}/voices`,
      },
      {
        source: "/api/jobs/my",
        destination: `${backendUrl}/jobs/my`,
      },
      {
        source: "/api/jobs/check/:tool_group",
        destination: `${backendUrl}/jobs/check/:tool_group`,
      },
      {
        source: "/api/jobs/:job_uuid",
        destination: `${backendUrl}/jobs/:job_uuid`,
      },
      {
        source: "/api/jobs/:job_uuid/download",
        destination: `${backendUrl}/jobs/:job_uuid/download`,
      },
      {
        source: "/api/script",
        destination: `${backendUrl}/script`,
      },
      {
        source: "/api/video-dubbing",
        destination: `${backendUrl}/video-dubbing`,
      },
      {
        source: "/api/screencast",
        destination: `${backendUrl}/screencast`,
      },
      {
        source: "/api/screencast/:path*",
        destination: `${backendUrl}/screencast/:path*`,
      },
      {
        source: "/docs",
        destination: `${backendUrl}/docs`,
      },
      {
        source: "/redoc",
        destination: `${backendUrl}/redoc`,
      },
      {
        source: "/openapi.json",
        destination: `${backendUrl}/openapi.json`,
      },
    ];
  },
};

export default nextConfig;
