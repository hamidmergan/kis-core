import { backendApi, parseDetail, genericErrorMessage } from "@/lib/api";
import type { Collection, OwnPage, Page, PagesList, SharedPage } from "./types";

/** The calls of the pages tool, all through the session cookie like the rest of KIS. */

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(parseDetail(body.detail, genericErrorMessage()));
  }
  return res.json();
}

const send = (path: string, method: "PUT" | "DELETE", body?: unknown) =>
  backendApi.fetch(path, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

export const listPages = () => backendApi.fetch("/pages").then((r) => json<PagesList>(r));
export const getPage = (uuid: string) => backendApi.fetch(`/pages/${uuid}`).then((r) => json<OwnPage>(r));
export const savePage = (uuid: string, page: Page) =>
  send(`/pages/${uuid}`, "PUT", page).then((r) => json<{ page: Page }>(r));
export const setShare = (uuid: string, on: boolean) =>
  send(`/pages/${uuid}/share`, "PUT", { on }).then((r) =>
    json<{ shared: boolean; code: string | null; collection: { code: string; count: number } }>(r));
export const deletePage = (uuid: string) => send(`/jobs/${uuid}`, "DELETE").then((r) => json<unknown>(r));
export const getShared = (code: string) =>
  backendApi.fetch(`/pages/shared/${code}`).then((r) => json<SharedPage>(r));
export const getCollection = (code: string) =>
  backendApi.fetch(`/pages/collection/${code}`).then((r) => json<Collection>(r));

/** Where a picture of a page is served, the owner's route or the shared one. */
export function imageBase(source: { uuid: string } | { code: string }): string {
  return "uuid" in source ? `/api/pages/${source.uuid}/images` : `/api/pages/shared/${source.code}/images`;
}

/** The link others open, on this very KIS. */
export function shareUrl(code: string): string {
  return `${window.location.origin}/p/${code}`;
}

export function collectionUrl(code: string): string {
  return `${window.location.origin}/u/${code}`;
}
