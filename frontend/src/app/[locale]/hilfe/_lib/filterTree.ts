import type { HelpGroup } from "./articles";

/** Hides admin groups without the right and narrows the tree to the query. */
export function filterTree(tree: HelpGroup[], query: string, isAdmin: boolean): HelpGroup[] {
  const needle = query.trim().toLowerCase();
  return tree
    .filter((group) => isAdmin || !group.adminOnly)
    .map((group) => {
      if (!needle) return group;
      if (group.title.toLowerCase().includes(needle)) return group;
      return { ...group, articles: group.articles.filter((a) => a.title.toLowerCase().includes(needle)) };
    })
    .filter((group) => group.articles.length > 0);
}
