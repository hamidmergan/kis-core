/**
 * Central configuration for each tool:
 * - color: signature accent colour (dot, icon tint, job-list indicator)
 * - image: path relative to /public  (null = show icon fallback)
 * - jobTools: job.tool values that belong to this tool (for JobsPanel dots)
 */
export const TOOL_CONFIG: Record<string, { color: string; image: string | null; jobTools: string[] }> = {
  screencast: {
    color: "#7C3AED",   // Violet
    image: "/tools/screencast-img.png",
    jobTools: ["screencast_translate", "screencast_render", "screencast_auto"],
  },
  "screencast-demo": {
    color: "#7C3AED",
    image: null,
    jobTools: ["screencast_demo_render"],
  },
  translation: {
    color: "#0D9488",   // Teal
    image: "/tools/translate-img.png",
    jobTools: ["translation"],
  },
  tts: {
    color: "#D97706",   // Amber
    image: "/tools/tts-img.png",
    jobTools: ["tts"],
  },
  transcription: {
    color: "#0284C7",   // Sky blue
    image: "/tools/stt-img.png",
    jobTools: ["transcription"],
  },
  image: {
    color: "#059669",   // Emerald
    image: "/tools/image-img.png",
    jobTools: ["image_generate", "image_edit", "image_analyze"],
  },
  glossary: {
    color: "#475569",   // Slate
    image: "/tools/glossary-img.png",
    jobTools: ["glossary"],
  },
  summary: {
    color: "#E11D48",   // Rose
    image: "/tools/summarize-img.png",
    jobTools: ["summary"],
  },
  "ki-tutor": {
    color: "#004261",
    image: "/tools/rag-img.png",
    jobTools: [],
  },
};

/** Returns the tool config for a given job.tool string */
export function getToolConfigByJobTool(jobTool: string): { color: string } {
  for (const cfg of Object.values(TOOL_CONFIG)) {
    if (cfg.jobTools.includes(jobTool)) return cfg;
  }
  return { color: "#668DA0" };
}
