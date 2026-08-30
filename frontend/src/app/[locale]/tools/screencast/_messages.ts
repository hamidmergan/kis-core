import type { RenderFlowMessages } from "./_hooks/useScreencastRenderFlow";
import type { TranslateFlowMessages } from "./_hooks/useScreencastTranslateFlow";

type T = (key: string, values?: Record<string, string | number>) => string;

/** The texts the render flow shows, translated once in one place. */
export function renderFlowMessages(t: T, tCommon: T): RenderFlowMessages {
  return {
    stuck: t("rendering.stuck"),
    queue: t("rendering.queue"),
    reconnected: t("rendering.reconnected"),
    renderError: t("error.renderError"),
    retryFailed: t("error.retryFailed"),
    tooManyJobs: t("error.tooManyJobs"),
    jobFailed: t("error.jobFailed"),
    unknownError: tCommon("unknownError"),
    previousRenderBusy: t("error.previousRenderBusy"),
    renderLabel: (p) => {
      switch (p.kind) {
        case "queue": return t("rendering.queue");
        case "translatePresentation": return t("rendering.translatePresentation");
        case "extractSlides": return t("rendering.extractSlides");
        case "scripts": return p.total != null ? t("rendering.scriptsWithCount", { n: p.total }) : t("rendering.scripts");
        case "images": return t("rendering.images");
        case "tts": return p.current != null && p.total != null
          ? t("rendering.ttsWithProgress", { current: p.current, total: p.total })
          : t("rendering.tts");
        case "video": return p.current != null && p.total != null
          ? t("rendering.videoWithProgress", { current: p.current, total: p.total })
          : t("rendering.video");
        case "concat": return t("rendering.concat");
        case "subtitles": return t("rendering.subtitles");
        default: return t("rendering.fallback");
      }
    },
  };
}

/** The texts of the translation flow. */
export function translateFlowMessages(t: T, tCommon: T): TranslateFlowMessages {
  return {
    unknownError: tCommon("unknownError"),
    uploadError: t("error.uploadError"),
    downloadFailed: t("error.downloadFailed"),
    jobInOtherTab: t("error.jobInOtherTab"),
    jobDeleted: t("error.jobDeleted"),
  };
}
