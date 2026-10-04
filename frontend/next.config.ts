import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  // Standalone traegt nur mit, was der Code importiert. Die Doku liest ihre
  // Markdown-Dateien zur Laufzeit, ohne diese Zeile ist sie auf prod leer.
  outputFileTracingIncludes: {
    "/[locale]/manual": ["./src/content/docs/**/*"],
    "/[locale]/manual/[slug]": ["./src/content/docs/**/*"],
  },
  // Ein Probe-Build darf den laufenden Dev-Server nicht abschiessen: beide
  // schreiben sonst in dasselbe .next und :3000 ist danach kaputt. Mit
  // NEXT_DIST_DIR=.next-verify baut die Probe daneben. Next schreibt dabei
  // next-env.d.ts und tsconfig.json auf den Probe-Ordner um, die beiden also
  // hinterher zuruecksetzen (git checkout).
  ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}),
  reactStrictMode: true,
  webpack: (config) => {
    // Required for react-pdf (pdfjs-dist uses canvas which doesn't exist in SSR)
    config.resolve.alias.canvas = false;
    return config;
  },
  experimental: {
    middlewareClientMaxBodySize: "500mb",
    proxyTimeout: 600000, // 10 min – für lokale Ollama-Generierung
    optimizePackageImports: ["@phosphor-icons/react"],
  },
  async redirects() {
    // Alte deutsche Adressen, damit gemerkte Links und schon verschickte Einladungen weiter ankommen.
    return [
      // Aelteste Adresse der Kalender-Seite.
      { source: "/schedule", destination: "/calendar", permanent: false },
      { source: "/:locale(de|en)/schedule", destination: "/:locale/calendar", permanent: false },
      { source: "/kalender", destination: "/calendar", permanent: false },
      { source: "/:locale(de|en)/kalender", destination: "/:locale/calendar", permanent: false },

      { source: "/zugang", destination: "/redeem", permanent: false },
      { source: "/:locale(de|en)/zugang", destination: "/:locale/redeem", permanent: false },
      { source: "/zugang/abgelaufen", destination: "/redeem/expired", permanent: false },
      { source: "/:locale(de|en)/zugang/abgelaufen", destination: "/:locale/redeem/expired", permanent: false },

      // Traegt ein Token, das schon an echte Personen verschickt wurde, muss unbedingt weiter ankommen.
      { source: "/einladung/:token", destination: "/invite/:token", permanent: false },
      { source: "/:locale(de|en)/einladung/:token", destination: "/:locale/invite/:token", permanent: false },

      { source: "/schnittstellen", destination: "/interfaces", permanent: false },
      { source: "/:locale(de|en)/schnittstellen", destination: "/:locale/interfaces", permanent: false },
      { source: "/wartung", destination: "/maintenance", permanent: false },
      { source: "/:locale(de|en)/wartung", destination: "/:locale/maintenance", permanent: false },

      // Einzelne Unterseiten zuerst, sonst greift die Sammelregel darunter und der Slug bleibt deutsch.
      { source: "/admin/nutzer/ausstehend", destination: "/admin/users/pending", permanent: false },
      { source: "/:locale(de|en)/admin/nutzer/ausstehend", destination: "/:locale/admin/users/pending", permanent: false },
      { source: "/admin/nutzer/einladungen", destination: "/admin/users/invites", permanent: false },
      { source: "/:locale(de|en)/admin/nutzer/einladungen", destination: "/:locale/admin/users/invites", permanent: false },
      { source: "/admin/nutzer/zugangscodes", destination: "/admin/users/access-codes", permanent: false },
      { source: "/:locale(de|en)/admin/nutzer/zugangscodes", destination: "/:locale/admin/users/access-codes", permanent: false },
      { source: "/admin/nutzer/alle-nutzer", destination: "/admin/users/all", permanent: false },
      { source: "/:locale(de|en)/admin/nutzer/alle-nutzer", destination: "/:locale/admin/users/all", permanent: false },
      { source: "/admin/nutzer/rollen", destination: "/admin/users/roles", permanent: false },
      { source: "/:locale(de|en)/admin/nutzer/rollen", destination: "/:locale/admin/users/roles", permanent: false },
      { source: "/admin/nutzer/kontingente", destination: "/admin/users/quotas", permanent: false },
      { source: "/:locale(de|en)/admin/nutzer/kontingente", destination: "/:locale/admin/users/quotas", permanent: false },
      { source: "/admin/werkzeuge/freigabe", destination: "/admin/tools/release", permanent: false },
      { source: "/:locale(de|en)/admin/werkzeuge/freigabe", destination: "/:locale/admin/tools/release", permanent: false },
      { source: "/admin/werkzeuge/auftraege", destination: "/admin/tools/jobs", permanent: false },
      { source: "/:locale(de|en)/admin/werkzeuge/auftraege", destination: "/:locale/admin/tools/jobs", permanent: false },
      { source: "/admin/werkzeuge/grenzen", destination: "/admin/tools/limits", permanent: false },
      { source: "/:locale(de|en)/admin/werkzeuge/grenzen", destination: "/:locale/admin/tools/limits", permanent: false },
      { source: "/admin/ki-assistent/quellen", destination: "/admin/ai-assistant/sources", permanent: false },
      { source: "/:locale(de|en)/admin/ki-assistent/quellen", destination: "/:locale/admin/ai-assistant/sources", permanent: false },
      { source: "/admin/ki-assistent/sprachniveau", destination: "/admin/ai-assistant/level", permanent: false },
      { source: "/:locale(de|en)/admin/ki-assistent/sprachniveau", destination: "/:locale/admin/ai-assistant/level", permanent: false },
      { source: "/admin/ki-assistent/einstufung", destination: "/admin/ai-assistant/assessment", permanent: false },
      { source: "/:locale(de|en)/admin/ki-assistent/einstufung", destination: "/:locale/admin/ai-assistant/assessment", permanent: false },
      { source: "/admin/ki-assistent/ki-verhalten", destination: "/admin/ai-assistant/behaviour", permanent: false },
      { source: "/:locale(de|en)/admin/ki-assistent/ki-verhalten", destination: "/:locale/admin/ai-assistant/behaviour", permanent: false },
      { source: "/admin/anbieter/liste", destination: "/admin/providers/list", permanent: false },
      { source: "/:locale(de|en)/admin/anbieter/liste", destination: "/:locale/admin/providers/list", permanent: false },
      { source: "/admin/anbieter/funktionen", destination: "/admin/providers/routes", permanent: false },
      { source: "/:locale(de|en)/admin/anbieter/funktionen", destination: "/:locale/admin/providers/routes", permanent: false },
      { source: "/admin/statistik/meine-module", destination: "/admin/stats/my-modules", permanent: false },
      { source: "/:locale(de|en)/admin/statistik/meine-module", destination: "/:locale/admin/stats/my-modules", permanent: false },
      { source: "/admin/statistik/nutzer", destination: "/admin/stats/users", permanent: false },
      { source: "/:locale(de|en)/admin/statistik/nutzer", destination: "/:locale/admin/stats/users", permanent: false },
      { source: "/admin/statistik/werkzeuge", destination: "/admin/stats/tools", permanent: false },
      { source: "/:locale(de|en)/admin/statistik/werkzeuge", destination: "/:locale/admin/stats/tools", permanent: false },
      { source: "/admin/statistik/ki-assistent", destination: "/admin/stats/ai-assistant", permanent: false },
      { source: "/:locale(de|en)/admin/statistik/ki-assistent", destination: "/:locale/admin/stats/ai-assistant", permanent: false },
      { source: "/admin/statistik/modelle", destination: "/admin/stats/models", permanent: false },
      { source: "/:locale(de|en)/admin/statistik/modelle", destination: "/:locale/admin/stats/models", permanent: false },

      // Die Profilseite zeigt nur noch das Sprachlevel und heisst seit 04.09.2026 so.
      { source: "/profile", destination: "/language-level", permanent: false },
      { source: "/:locale(de|en)/profile", destination: "/:locale/language-level", permanent: false },
      { source: "/profile/language-test", destination: "/language-level/test", permanent: false },
      { source: "/:locale(de|en)/profile/language-test", destination: "/:locale/language-level/test", permanent: false },

      // Admin-Unterseiten, nur die Slugs wurden englisch, key/labelKey blieben unangetastet.
      { source: "/admin/nutzer/:path*", destination: "/admin/users/:path*", permanent: false },
      { source: "/:locale(de|en)/admin/nutzer/:path*", destination: "/:locale/admin/users/:path*", permanent: false },
      { source: "/admin/werkzeuge/:path*", destination: "/admin/tools/:path*", permanent: false },
      { source: "/:locale(de|en)/admin/werkzeuge/:path*", destination: "/:locale/admin/tools/:path*", permanent: false },
      { source: "/admin/ki-assistent/:path*", destination: "/admin/ai-assistant/:path*", permanent: false },
      { source: "/:locale(de|en)/admin/ki-assistent/:path*", destination: "/:locale/admin/ai-assistant/:path*", permanent: false },
      { source: "/admin/anbieter/:path*", destination: "/admin/providers/:path*", permanent: false },
      { source: "/:locale(de|en)/admin/anbieter/:path*", destination: "/:locale/admin/providers/:path*", permanent: false },
      { source: "/admin/statistik", destination: "/admin/stats", permanent: false },
      { source: "/:locale(de|en)/admin/statistik", destination: "/:locale/admin/stats", permanent: false },
      { source: "/admin/maskottchen/:path*", destination: "/admin/mascots/:path*", permanent: false },
      { source: "/:locale(de|en)/admin/maskottchen/:path*", destination: "/:locale/admin/mascots/:path*", permanent: false },
    ];
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
        source: "/api/health/maintenance",
        destination: `${backendUrl}/health/maintenance`,
      },
      {
        source: "/api/health/labels",
        destination: `${backendUrl}/health/labels`,
      },
      {
        source: "/translate/config",
        destination: `${backendUrl}/translate/config`,
      },
      {
        source: "/api/translate/config",
        destination: `${backendUrl}/translate/config`,
      },
      {
        source: "/api/interpreter/:path*",
        destination: `${backendUrl}/interpreter/:path*`,
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
        source: "/api/tts/providers-with-voices",
        destination: `${backendUrl}/tts/providers-with-voices`,
      },
      {
        source: "/api/tts/providers/:id/preview",
        destination: `${backendUrl}/tts/providers/:id/preview`,
      },
      {
        source: "/api/tts/providers",
        destination: `${backendUrl}/tts/providers`,
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
        source: "/api/admin/:path*",
        destination: `${backendUrl}/admin/:path*`,
      },
      {
        source: "/api/feedback",
        destination: `${backendUrl}/feedback`,
      },
      {
        source: "/api/invites/:path*",
        destination: `${backendUrl}/invites/:path*`,
      },
      {
        source: "/api/access-codes/:path*",
        destination: `${backendUrl}/access-codes/:path*`,
      },
      {
        source: "/api/event/:path*",
        destination: `${backendUrl}/event/:path*`,
      },
      {
        source: "/api/evaluation/:path*",
        destination: `${backendUrl}/evaluation/:path*`,
      },
      {
        source: "/api/me/:path*",
        destination: `${backendUrl}/me/:path*`,
      },
      {
        source: "/api/me",
        destination: `${backendUrl}/me`,
      },
      {
        source: "/api/campus/:path*",
        destination: `${backendUrl}/campus/:path*`,
      },
      {
        source: "/api/glossaries/:path*",
        destination: `${backendUrl}/glossaries/:path*`,
      },
      {
        source: "/api/glossaries",
        destination: `${backendUrl}/glossaries`,
      },
      {
        source: "/api/jobs/my",
        destination: `${backendUrl}/jobs/my`,
      },
      {
        source: "/api/jobs/stream",
        destination: `${backendUrl}/jobs/stream`,
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
        source: "/api/jobs/:job_uuid/pptx",
        destination: `${backendUrl}/jobs/:job_uuid/pptx`,
      },
      {
        source: "/api/jobs/:job_uuid/docx",
        destination: `${backendUrl}/jobs/:job_uuid/docx`,
      },
      {
        source: "/api/jobs/:job_uuid/bundle",
        destination: `${backendUrl}/jobs/:job_uuid/bundle`,
      },
      {
        source: "/api/jobs/:job_uuid/subtitles",
        destination: `${backendUrl}/jobs/:job_uuid/subtitles`,
      },
      {
        source: "/api/jobs/:job_uuid/video",
        destination: `${backendUrl}/jobs/:job_uuid/video`,
      },
      {
        source: "/api/jobs/:job_uuid/cancel",
        destination: `${backendUrl}/jobs/:job_uuid/cancel`,
      },
      {
        source: "/api/jobs/:job_uuid/retry",
        destination: `${backendUrl}/jobs/:job_uuid/retry`,
      },
      {
        source: "/api/transcription/providers",
        destination: `${backendUrl}/transcription/providers`,
      },
      {
        source: "/api/transcription",
        destination: `${backendUrl}/transcription`,
      },
      {
        source: "/api/summary/providers",
        destination: `${backendUrl}/summary/providers`,
      },
      {
        source: "/api/summary/templates",
        destination: `${backendUrl}/summary/templates`,
      },
      {
        source: "/api/summary/measure",
        destination: `${backendUrl}/summary/measure`,
      },
      {
        source: "/api/summary/measure/workspace",
        destination: `${backendUrl}/summary/measure/workspace`,
      },
      {
        source: "/api/summary",
        destination: `${backendUrl}/summary`,
      },
      {
        source: "/api/image/:path*",
        destination: `${backendUrl}/image/:path*`,
      },
      {
        source: "/api/script",
        destination: `${backendUrl}/script`,
      },
      {
        source: "/api/podcast/:path*",
        destination: `${backendUrl}/podcast/:path*`,
      },
      {
        source: "/api/praesentation/:path*",
        destination: `${backendUrl}/praesentation/:path*`,
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
        source: "/api/screencast-demo/:path*",
        destination: `${backendUrl}/screencast-demo/:path*`,
      },
      {
        source: "/api/summary-demo/:path*",
        destination: `${backendUrl}/summary-demo/:path*`,
      },
      {
        source: "/api/praesentation-demo/:path*",
        destination: `${backendUrl}/praesentation-demo/:path*`,
      },
      {
        source: "/api/podcast-demo/:path*",
        destination: `${backendUrl}/podcast-demo/:path*`,
      },
      {
        source: "/api/ai-assistant/:path*",
        destination: `${backendUrl}/ai-assistant/:path*`,
      },
      {
        source: "/manual",
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

export default withNextIntl(nextConfig);
